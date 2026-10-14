#!/usr/bin/env python3
"""Verificador de pre-voo (plano v2, secao 7.10).

Antes de CADA rodada o runner chama `verificar(...)`. Se qualquer item
reprovar, a rodada nao comeca (nenhum credito e gasto) e o motivo e impresso.

O que "esta certo" vem de `protocolo/congelamento.json`, gerado UMA vez, depois
que voce validou o ambiente, com:

    python3 orchestrator/preflight.py --gerar-congelamento

Para ver o estado atual sem rodar nada:

    python3 orchestrator/preflight.py --verificar-ambiente
"""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CONGELAMENTO = RAIZ / "protocolo" / "congelamento.json"
FIXTURES = RAIZ / "fixtures"
PROMPTS = RAIZ / "prompts"
IGNORAR = ("node_modules", "dist", ".git", "prompt.txt")
PROIBIDOS_NO_HOME = {".claude", ".claude.json", "CLAUDE.md", "AGENTS.md", ".agents", ".config"}
PERMITIDOS_NO_HOME = {"opencode.json", ".codex"}
ESPACO_MINIMO_GB = 2


def _sha256_arquivo(caminho):
    h = hashlib.sha256()
    with caminho.open("rb") as f:
        for bloco in iter(lambda: f.read(65536), b""):
            h.update(bloco)
    return h.hexdigest()


def _sha256_arvore(raiz):
    h = hashlib.sha256()
    for arquivo in sorted(p for p in raiz.rglob("*") if p.is_file()):
        rel = arquivo.relative_to(raiz)
        if any(parte in IGNORAR for parte in rel.parts):
            continue
        h.update(str(rel).encode("utf-8"))
        h.update(arquivo.read_bytes())
    return h.hexdigest()


def _hashes_fixtures():
    return {
        "lockfiles": {c: _sha256_arquivo(FIXTURES / f"{c}-base" / "package-lock.json")
                      for c in ("site", "jogo", "app")},
        "arvores": {c: _sha256_arvore(FIXTURES / f"{c}-base") for c in ("site", "jogo", "app")},
        "prompts": {p.name: _sha256_arquivo(p) for p in sorted(PROMPTS.glob("*.txt"))},
    }


def gerar_congelamento(args_runner, info):
    """Grava o estado que, a partir de agora, toda rodada deve reproduzir."""
    dados = {
        "gerado_em_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "image": args_runner.image,
        "image_id": info["image_id"],
        "versoes": info["versoes"],
        **_hashes_fixtures(),
    }
    CONGELAMENTO.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    return dados


def _item(nome, ok, detalhe=""):
    return {"item": nome, "ok": bool(ok), "detalhe": detalhe}


def _docker(*partes, timeout=60):
    return subprocess.run(["docker", *partes], capture_output=True, text=True, timeout=timeout)


def _checar_home(home):
    achados = []
    for caminho in home.rglob("*"):
        rel = caminho.relative_to(home)
        topo = rel.parts[0]
        if topo in PROIBIDOS_NO_HOME:
            achados.append(str(rel))
        elif topo not in PERMITIDOS_NO_HOME:
            achados.append(str(rel))
    return achados


def verificar(args, linha, workspace, home, prompt_path, modelo, info):
    """Devolve a lista de {item, ok, detalhe}. Qualquer ok=False aborta a rodada."""
    r = []

    # 0. congelamento existe
    if not CONGELAMENTO.exists():
        return [_item("congelamento", False,
                      "protocolo/congelamento.json nao existe: rode "
                      "`python3 orchestrator/preflight.py --gerar-congelamento`")]
    ref = json.loads(CONGELAMENTO.read_text(encoding="utf-8"))
    atual = _hashes_fixtures()

    # 1. imagem e versoes dos harnesses
    r.append(_item("imagem (id)", info["image_id"] and info["image_id"] == ref["image_id"],
                   f"atual={info['image_id']} congelado={ref['image_id']}"))
    r.append(_item("versoes dos harnesses e do Node", info["versoes"] == ref["versoes"],
                   f"atual={info['versoes']} congelado={ref['versoes']}"))

    # 2. HOME da rodada limpo
    sujeira = _checar_home(home)
    r.append(_item("HOME da rodada limpo", not sujeira, f"arquivos inesperados: {sujeira}" if sujeira else ""))

    # 3. workspace identico ao starter e sem node_modules herdado
    cenario = linha["cenario"]
    r.append(_item("workspace igual ao starter", _sha256_arvore(workspace) == ref["arvores"][cenario],
                   f"cenario={cenario}"))

    # 4. lockfile e prompt congelados
    r.append(_item("lockfile do starter", atual["lockfiles"][cenario] == ref["lockfiles"][cenario]))
    nome_prompt = Path(prompt_path).name
    r.append(_item("prompt congelado", atual["prompts"].get(nome_prompt) == ref["prompts"].get(nome_prompt),
                   nome_prompt))

    # 5. rede interna e sem saida para a internet
    insp = _docker("network", "inspect", args.network, "-f", "{{.Internal}}")
    r.append(_item("rede interna", insp.returncode == 0 and insp.stdout.strip() == "true",
                   f"{args.network}: {insp.stdout.strip() or insp.stderr.strip()}"))
    egress = _docker("run", "--rm", "--network", args.network, args.image, "bash", "-lc",
                     "curl -sS -m 5 -o /dev/null https://example.com", timeout=40)
    r.append(_item("sem saida para a internet", egress.returncode != 0,
                   "o conteiner CONSEGUIU acessar a internet" if egress.returncode == 0 else ""))

    # 6. roteador responde e expoe a rota do modelo
    rota = modelo[len("9router/"):] if modelo.startswith("9router/") else modelo
    ok_gw, det = False, "gateway nao configurado"
    if getattr(args, "gateway_url", None) and getattr(args, "api_key", None):
        try:
            req = urllib.request.Request(f"{args.gateway_url}/v1/models",
                                         headers={"Authorization": f"Bearer {args.api_key}"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                corpo = json.loads(resp.read().decode("utf-8"))
            ids = {m.get("id") for m in corpo.get("data", [])}
            ok_gw, det = rota in ids, f"rota {rota} {'presente' if rota in ids else 'AUSENTE'}"
        except Exception as e:  # noqa: BLE001
            det = f"erro: {e}"
    r.append(_item("roteador e rota do modelo", ok_gw, det))

    # 7. nenhum conteiner de rodada ativo
    ps = _docker("ps", "--filter", "name=tcc-", "-q")
    r.append(_item("nenhum conteiner tcc-* ativo", ps.returncode == 0 and not ps.stdout.strip(),
                   ps.stdout.strip()))

    # 8. repositorio limpo fora de dados/ e runs/
    git = subprocess.run(["git", "-C", str(RAIZ), "status", "--porcelain"],
                         capture_output=True, text=True)
    sujos = [l for l in git.stdout.splitlines()
             if not (l[3:].strip().strip('"').startswith(("dados/", "runs/")))]
    r.append(_item("repositorio sem alteracoes soltas", git.returncode == 0 and not sujos,
                   "; ".join(sujos[:5])))

    # 9. espaco em disco
    livre_gb = shutil.disk_usage(RAIZ).free / 1e9
    r.append(_item("espaco em disco", livre_gb >= ESPACO_MINIMO_GB, f"{livre_gb:.1f} GB livres"))
    return r


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gerar-congelamento", action="store_true")
    ap.add_argument("--verificar-ambiente", action="store_true",
                    help="compara o ambiente atual com o congelamento (sem rodar agente)")
    ap.add_argument("--image", default="tcc-harnesses:v1")
    args = ap.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import runner  # noqa: PLC0415

    ra = runner.montar_parser().parse_args(["--image", args.image])
    info = runner.info_imagem(ra)
    if args.gerar_congelamento:
        dados = gerar_congelamento(ra, info)
        print(f"gravado {CONGELAMENTO}")
        print(json.dumps({k: dados[k] for k in ("image_id", "versoes")}, indent=2, ensure_ascii=False))
        return
    if args.verificar_ambiente:
        if not CONGELAMENTO.exists():
            sys.exit("sem congelamento: rode --gerar-congelamento primeiro")
        ref = json.loads(CONGELAMENTO.read_text(encoding="utf-8"))
        atual = _hashes_fixtures()
        itens = [
            _item("imagem (id)", info["image_id"] == ref["image_id"]),
            _item("versoes", info["versoes"] == ref["versoes"]),
            _item("lockfiles", atual["lockfiles"] == ref["lockfiles"]),
            _item("starters", atual["arvores"] == ref["arvores"]),
            _item("prompts", atual["prompts"] == ref["prompts"]),
        ]
        for i in itens:
            print(("OK     " if i["ok"] else "FALHOU ") + i["item"])
        sys.exit(0 if all(i["ok"] for i in itens) else 1)
    ap.print_help()


if __name__ == "__main__":
    main()
