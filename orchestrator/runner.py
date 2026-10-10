#!/usr/bin/env python3
"""Orquestrador de rodadas do experimento (plano v2, secoes 7.8 a 7.14).

Executa a fila `dados/plano_162_execucoes.csv` em ambiente conteinerizado
isolado, seguindo `MANUAL-RODADAS.md` secao 4. Cada rodada gera a estrutura
completa de capturas (manifest, prompt, events, stderr, snapshot, summary).

Principios respeitados:
- Nenhum campo nao observado e inventado: o que nao existe vira `null`.
- Nao ha intervencao na solucao durante a rodada.
- O workspace e novo a cada rodada, copiado do starter.
- A avaliacao roda fora do alcance do agente, sobre o snapshot congelado.

Exemplos:
    python orchestrator/runner.py --dry-run --limit 3
    python orchestrator/runner.py --etapa 1
    python orchestrator/runner.py --run-id SITE-CODEX-HAIKU-P2-R01
    python orchestrator/runner.py --pilot
"""

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import normalizer  # noqa: E402
from adapters import HARNESSES, obter as obter_adapter  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
FILA = RAIZ / "dados" / "plano_162_execucoes.csv"
RESULTADOS = RAIZ / "dados" / "resultados.csv"
MODELOS = RAIZ / "orchestrator" / "modelos.json"
RUNS = RAIZ / "runs"
FIXTURES = RAIZ / "fixtures"
PROMPTS = RAIZ / "prompts"
VERSOES = RAIZ / "VERSOES.txt"
AVALIACAO = RAIZ / "avaliacao"
PILOTO_CSV = RAIZ / "protocolo" / "compatibilidade-piloto.csv"

CAMPOS_RESULTADOS = [
    "run_id", "etapa", "provider", "runtime_status", "duration_seconds",
    "input_tokens", "output_tokens", "cached_tokens", "cost_usd", "cost_method",
    "build_success", "tests_passed", "tests_total", "reference_quality",
    "prompt_adherence", "notes",
]

SECAO_HARNESS = {"claude-code": "Claude Code", "codex": "Codex", "opencode": "OpenCode"}


# --------------------------------------------------------------------------- #
# Utilitarios
# --------------------------------------------------------------------------- #
def agora_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_arquivo(caminho):
    if not caminho.exists():
        return None
    h = hashlib.sha256()
    with caminho.open("rb") as f:
        for bloco in iter(lambda: f.read(65536), b""):
            h.update(bloco)
    return h.hexdigest()


def sha256_arvore(raiz):
    h = hashlib.sha256()
    for arquivo in sorted(p for p in raiz.rglob("*") if p.is_file()):
        h.update(str(arquivo.relative_to(raiz)).encode("utf-8"))
        h.update(arquivo.read_bytes())
    return h.hexdigest()


def ler_versoes():
    dados = {}
    if not VERSOES.exists():
        return dados
    secao = None
    for linha in VERSOES.read_text(encoding="utf-8", errors="replace").splitlines():
        texto = linha.strip()
        if texto.startswith("===") and texto.endswith("==="):
            secao = texto.strip("=").strip()
            dados[secao] = []
        elif texto and secao is not None:
            dados[secao].append(texto)
    return dados


def versao_harness(versoes, harness):
    valores = versoes.get(SECAO_HARNESS.get(harness, ""), [])
    return valores[0] if valores else None


def git_head():
    try:
        saida = subprocess.run(
            ["git", "-C", str(RAIZ), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        )
        return saida.stdout.strip()
    except Exception:
        return None


def ler_fila():
    with FILA.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def escrever_fila(linhas):
    campos = ["ordem", "etapa", "condicional", "run_id", "cenario", "harness",
              "modelo_rotulo", "modelo_id", "provedor", "prompt", "repeticao", "status"]
    with FILA.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(linhas)


def marcar_status_fila(run_id, status):
    linhas = ler_fila()
    for linha in linhas:
        if linha["run_id"] == run_id:
            linha["status"] = status
    escrever_fila(linhas)


def carregar_modelos():
    if MODELOS.exists():
        return json.loads(MODELOS.read_text(encoding="utf-8"))
    return {}


def detectar_gateway(args):
    """Descobre o endereco do 9router alcancavel pela rede isolada."""
    if getattr(args, "no_gateway", False):
        return None
    host = args.gateway_host
    if not host:
        try:
            host = subprocess.run(
                ["docker", "network", "inspect", args.network,
                 "-f", "{{(index .IPAM.Config 0).Gateway}}"],
                capture_output=True, text=True, check=True).stdout.strip()
        except Exception:
            host = None
    if not host:
        return None
    return f"http://{host}:{args.gateway_port}"


def ler_chave(args):
    if getattr(args, "no_gateway", False):
        return None
    caminho = Path(args.api_key_file).expanduser()
    if caminho.exists():
        return caminho.read_text(encoding="utf-8").strip()
    return None


ORG_ROTA = {"openai": "openai", "anthropic": "anthropic", "relace": "deepseek"}


def resolver_modelo(harness, provedor, modelo_id, tabela):
    """Resolve o identificador de modelo aceito pelo harness.

    O 9router expoe os modelos como `openrouter/<org>/<slug>`; o OpenCode usa
    o prefixo do provedor configurado (`9router/`). Os valores exatos ficam em
    `orchestrator/modelos.json`, confirmados no piloto.
    """
    chave = f"{harness}:{provedor}:{modelo_id}"
    if tabela.get(chave):
        return tabela[chave]
    rota = f"openrouter/{ORG_ROTA.get(provedor, provedor)}/{modelo_id}"
    return f"9router/{rota}" if harness == "opencode" else rota


def registrar_resultado(resumo):
    linhas = []
    if RESULTADOS.exists() and RESULTADOS.stat().st_size:
        with RESULTADOS.open("r", encoding="utf-8", newline="") as f:
            linhas = list(csv.DictReader(f))
    linhas = [l for l in linhas if l.get("run_id") != resumo["run_id"]]
    linha = {campo: resumo.get(campo) for campo in CAMPOS_RESULTADOS}
    linhas.append(linha)
    with RESULTADOS.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS_RESULTADOS)
        w.writeheader()
        w.writerows(linhas)


# --------------------------------------------------------------------------- #
# Preparacao do ambiente da rodada
# --------------------------------------------------------------------------- #
def preparar_workspace(run_id, cenario, dry_run=False):
    src = FIXTURES / f"{cenario}-base"
    dst = RUNS / run_id / "workspace"
    if not src.exists():
        raise FileNotFoundError(f"starter ausente: {src}")
    if dst.exists():
        shutil.rmtree(dst)
    if dry_run:
        dst.mkdir(parents=True, exist_ok=True)
    else:
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns(".git", "dist"))
    return dst


def preparar_home(run_id, harness, dry_run=False, modelo=None, gateway_url=None, api_key=None):
    home = RUNS / run_id / "home"
    home.mkdir(parents=True, exist_ok=True)
    if dry_run:
        return home

    if harness == "opencode":
        modelo_no_provedor = modelo
        if modelo_no_provedor and modelo_no_provedor.startswith("9router/"):
            modelo_no_provedor = modelo_no_provedor[len("9router/"):]
        config = {
            "$schema": "https://opencode.ai/config.json",
            "tools": {"webfetch": False},
            "provider": {},
        }
        if gateway_url:
            config["provider"]["9router"] = {
                "npm": "@ai-sdk/openai-compatible",
                "name": "9router",
                "options": {"baseURL": f"{gateway_url}/v1", "apiKey": api_key or ""},
                "models": {modelo_no_provedor: {"name": modelo_no_provedor}}
                if modelo_no_provedor else {},
            }
            if modelo:
                config["model"] = modelo
        (home / "opencode.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    elif harness == "codex":
        (home / ".codex").mkdir(exist_ok=True)
        linhas = []
        if gateway_url:
            linhas += [
                f'model = "{modelo}"' if modelo else "",
                'model_provider = "9router"',
                "",
                "[model_providers.9router]",
                'name = "9router"',
                f'base_url = "{gateway_url}/v1"',
                'wire_api = "responses"',
                'env_key = "OPENAI_API_KEY"',
                "",
            ]
        linhas += ["[tools]", "web_search = false", ""]
        (home / ".codex" / "config.toml").write_text(
            "\n".join(linhas), encoding="utf-8")
    return home


def gravar_manifest(run_id, linha, workspace, prompt_path, args, versoes):
    lock = FIXTURES / f"{linha['cenario']}-base" / "package-lock.json"
    manifest = {
        "run_id": run_id,
        "scenario": linha["cenario"],
        "harness": linha["harness"],
        "model_label": linha["modelo_rotulo"],
        "model_id": linha["modelo_id"],
        "provider": linha["provedor"],
        "gateway": args.gateway,
        "started_at_utc": agora_utc(),
        "harness_version": versao_harness(versoes, linha["harness"]),
        "router_version": args.router_version,
        "runtime_version": args.runtime_version,
        "browser_version": args.browser_version,
        "image": args.image,
        "scenario_commit_sha": git_head(),
        "scenario_lockfile_sha256": sha256_arquivo(lock),
        "prompt_sha256": sha256_arquivo(prompt_path),
        "time_limit_seconds": args.time_limit,
        "iteration_limit": args.iteration_limit,
        "cost_limit_usd": args.cost_limit,
        "network_policy": f"isolado ({args.network}); saida apenas para o roteador",
    }
    caminho = RUNS / run_id / "manifest.json"
    if not args.dry_run:
        caminho.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


# --------------------------------------------------------------------------- #
# Execucao no container
# --------------------------------------------------------------------------- #
def montar_docker(args, workspace, home, comando):
    cmd = [
        "docker", "run", "--rm", "--network", args.network,
        "-v", f"{workspace}:/home/executor/trabalho",
        "-v", f"{home}:/home/executor",
        "-e", "HOME=/home/executor",
        "-e", "OPENCODE_CONFIG=/home/executor/opencode.json",
        "-w", "/home/executor/trabalho",
    ]
    gateway_url = getattr(args, "gateway_url", None)
    api_key = getattr(args, "api_key", None)
    if gateway_url and api_key:
        cmd += [
            "-e", f"OPENAI_BASE_URL={gateway_url}/v1",
            "-e", f"OPENAI_API_KEY={api_key}",
            "-e", f"ANTHROPIC_BASE_URL={gateway_url}",
            "-e", f"ANTHROPIC_API_KEY={api_key}",
            "-e", f"ANTHROPIC_AUTH_TOKEN={api_key}",
        ]
    cmd += [args.image, "bash", "-lc", comando]
    return cmd


def executar_no_container(args, workspace, home, comando, run_dir):
    events = run_dir / "events.jsonl"
    stderr = run_dir / "stderr.log"
    if args.dry_run:
        print("  [dry-run] docker " + " ".join(montar_docker(args, workspace, home, comando)[1:]))
        return {"returncode": None, "timed_out": False, "duration_seconds": None}

    inicio = time.monotonic()
    timed_out = False
    returncode = None
    try:
        with events.open("wb") as fo, stderr.open("wb") as fe:
            proc = subprocess.run(
                montar_docker(args, workspace, home, comando),
                stdout=fo, stderr=fe, timeout=args.time_limit,
            )
            returncode = proc.returncode
    except subprocess.TimeoutExpired:
        timed_out = True
    duracao = round(time.monotonic() - inicio, 3)
    return {"returncode": returncode, "timed_out": timed_out, "duration_seconds": duracao}


def classificar_status(res, stderr_texto):
    if res["timed_out"]:
        return "timeout", None
    texto = (stderr_texto or "").lower()
    if any(p in texto for p in ("insufficient", "credit", "payment required", " 402")):
        return "aborted", "credit_exhausted"
    if any(p in texto for p in ("rate limit", "429", "500 ", "502", "503", "api error",
                                "provider", "overloaded", "unavailable")):
        return "provider_error", None
    if res["returncode"] == 0:
        return "completed", None
    return "harness_error", None


# --------------------------------------------------------------------------- #
# Avaliacao independente
# --------------------------------------------------------------------------- #
def rodar_avaliador(run_id, cenario, prompt_level):
    """Roda o avaliador independente sobre o snapshot congelado.

    O avaliador ainda nao existe (ver ESTADO.md). Se `avaliacao/avaliar.py`
    existir, ele e chamado; senao, os campos de qualidade ficam `null`.
    Usa `avaliacao/score.py` sobre o `test-results.json` quando presente.
    """
    run_dir = RUNS / run_id
    campos = {
        "build_success": None, "tests_passed": None, "tests_total": None,
        "reference_quality": None, "prompt_adherence": None,
    }
    test_results = run_dir / "test-results.json"

    avaliador = AVALIACAO / "avaliar.py"
    if avaliador.exists():
        try:
            subprocess.run(
                [sys.executable, str(avaliador), str(run_dir / "source-snapshot"),
                 cenario, str(run_dir)],
                capture_output=True, text=True, timeout=1800, check=False,
            )
        except Exception as e:  # noqa: BLE001
            print(f"  [avaliador] falhou: {e}")

    if not test_results.exists():
        return campos

    soma = None
    if (AVALIACAO / "score.py").exists():
        try:
            out = subprocess.run(
                [sys.executable, str(AVALIACAO / "score.py"),
                 str(test_results), cenario, str(prompt_level)],
                capture_output=True, text=True, check=False,
            )
            if out.returncode == 0:
                soma = json.loads(out.stdout)
        except Exception:  # noqa: BLE001
            soma = None

    if soma:
        campos["reference_quality"] = soma.get("referencia_B", {}).get("observada")
        campos["prompt_adherence"] = soma.get("aderencia_A", {}).get("observada")
        dados = json.loads(test_results.read_text(encoding="utf-8"))
        criterios = dados.get("criterios", [])
        campos["tests_total"] = len(criterios)
        campos["tests_passed"] = sum(1 for c in criterios if c.get("passou") == 1)
    return campos


# --------------------------------------------------------------------------- #
# Processamento de uma rodada
# --------------------------------------------------------------------------- #
def processar_linha(linha, args, versoes, tabela_modelos):
    run_id = linha["run_id"]
    run_dir = RUNS / run_id
    resumo_previo = run_dir / "summary.json"
    if resumo_previo.exists() and not args.force:
        print(f"[pular] {run_id} (summary.json ja existe; use --force para refazer)")
        return

    run_dir.mkdir(parents=True, exist_ok=True)
    prompt_origem = PROMPTS / f"{linha['cenario']}-p{linha['prompt']}.txt"
    if not prompt_origem.exists():
        print(f"[erro] prompt ausente: {prompt_origem}")
        return

    modelo = resolver_modelo(linha["harness"], linha["provedor"], linha["modelo_id"], tabela_modelos)
    workspace = preparar_workspace(run_id, linha["cenario"], args.dry_run)
    home = preparar_home(run_id, linha["harness"], args.dry_run, modelo,
                         getattr(args, "gateway_url", None), getattr(args, "api_key", None))

    prompt_txt = run_dir / "prompt.txt"
    if not args.dry_run:
        shutil.copy(prompt_origem, prompt_txt)
        shutil.copy(prompt_origem, workspace / "prompt.txt")

    manifest = gravar_manifest(run_id, linha, workspace, prompt_origem, args, versoes)

    adapter = obter_adapter(linha["harness"])
    comando = adapter.build_command(modelo)

    print(f"[rodar] {run_id}: {adapter.NOME} / {modelo} / P{linha['prompt']}")
    resultado = executar_no_container(args, workspace, home, comando, run_dir)
    if args.dry_run:
        return

    # Congelar a solucao (sem o prompt.txt, que nao faz parte do artefato).
    (workspace / "prompt.txt").unlink(missing_ok=True)
    snapshot = run_dir / "source-snapshot"
    if snapshot.exists():
        shutil.rmtree(snapshot)
    shutil.copytree(workspace, snapshot)
    (run_dir / "source-snapshot.sha256").write_text(sha256_arvore(snapshot), encoding="utf-8")

    stderr_texto = ""
    if (run_dir / "stderr.log").exists():
        stderr_texto = (run_dir / "stderr.log").read_text(encoding="utf-8", errors="replace")
    runtime_status, motivo = classificar_status(resultado, stderr_texto)

    agregado = normalizer.normalizar_run(run_dir)
    qualidade = rodar_avaliador(run_id, linha["cenario"], linha["prompt"])

    resumo = {
        "run_id": run_id,
        "scenario": linha["cenario"],
        "harness": linha["harness"],
        "model_label": linha["modelo_rotulo"],
        "model_id": linha["modelo_id"],
        "provider": linha["provedor"],
        "gateway": args.gateway,
        "prompt_level": int(linha["prompt"]),
        "repetition": int(linha["repeticao"]),
        "started_at_utc": manifest["started_at_utc"],
        "finished_at_utc": agora_utc(),
        "scenario_commit_sha": manifest["scenario_commit_sha"],
        "harness_version": manifest["harness_version"],
        "prompt_sha256": manifest["prompt_sha256"],
        "runtime_status": runtime_status,
        "duration_seconds": resultado["duration_seconds"],
        "input_tokens": agregado["input_tokens"],
        "output_tokens": agregado["output_tokens"],
        "cached_tokens": agregado["cached_tokens"],
        "cost_usd": agregado["cost_usd"],
        "cost_method": "medido (metadados do roteador)" if agregado["cost_usd"] is not None else None,
        "tool_calls": agregado["tool_calls"],
        "test_executions_by_agent": agregado["test_executions_by_agent"],
        "verified_self_corrections": None,
        "manual_interventions": 0,
        "build_success": qualidade["build_success"],
        "tests_passed": qualidade["tests_passed"],
        "tests_total": qualidade["tests_total"],
        "reference_quality": qualidade["reference_quality"],
        "prompt_adherence": qualidade["prompt_adherence"],
        "notes": motivo,
        "exit_code": resultado["returncode"],
        "events_lidos": agregado["eventos_lidos"],
        "linhas_invalidas": agregado["linhas_invalidas"],
    }
    (run_dir / "summary.json").write_text(
        json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")

    registrar_resultado(resumo)
    marcar_status_fila(run_id, runtime_status)
    print(f"  status={runtime_status} duracao={resultado['duration_seconds']}s "
          f"tool_calls={agregado['tool_calls']}")


# --------------------------------------------------------------------------- #
# Fila principal
# --------------------------------------------------------------------------- #
def selecionar_linhas(args):
    linhas = ler_fila()
    if args.run_id:
        linhas = [l for l in linhas if l["run_id"] == args.run_id]
    if args.etapa:
        linhas = [l for l in linhas if int(l["etapa"]) == args.etapa]
    if not args.force:
        linhas = [l for l in linhas if l["status"] in ("planejada", "provider_error", "harness_error", "timeout", "aborted")]
    if args.limit:
        linhas = linhas[: args.limit]
    return linhas


def rodar_fila(args, versoes, tabela_modelos):
    linhas = selecionar_linhas(args)
    if not linhas:
        print("nada a executar")
        return
    print(f"{len(linhas)} rodada(s) selecionada(s)")
    for i, linha in enumerate(linhas, 1):
        print(f"--- [{i}/{len(linhas)}] ---")
        try:
            processar_linha(linha, args, versoes, tabela_modelos)
        except Exception as e:  # noqa: BLE001
            print(f"[erro] {linha['run_id']}: {e}")
            marcar_status_fila(linha["run_id"], "harness_error")


# --------------------------------------------------------------------------- #
# Piloto de compatibilidade (secao 7.12)
# --------------------------------------------------------------------------- #
PILOTO_README = "# Projeto piloto\n\nPrimeira linha do README de compatibilidade.\n"
PILOTO_SOMA_BUG = "export function soma(a, b) {\n  return a - b;\n}\n"
PILOTO_TESTE = (
    "import { soma } from './soma.mjs';\n"
    "if (soma(2, 3) === 5) { console.log('OK'); process.exit(0); }\n"
    "console.error('FALHOU'); process.exit(1);\n"
)


def preparar_workspace_piloto(base):
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True)
    (base / "README.md").write_text(PILOTO_README, encoding="utf-8")
    (base / "soma.mjs").write_text(PILOTO_SOMA_BUG, encoding="utf-8")
    (base / "test.mjs").write_text(PILOTO_TESTE, encoding="utf-8")
    return base


def _eventos_validos(run_dir):
    caminho = run_dir / "events.jsonl"
    total, uso = 0, None
    if caminho.exists():
        for linha in caminho.read_text(encoding="utf-8", errors="replace").splitlines():
            linha = linha.strip()
            if not linha:
                continue
            try:
                evento = json.loads(linha)
            except json.JSONDecodeError:
                continue
            total += 1
            uso = normalizer.extrair_uso(evento) or uso
    return total, uso


def _rodar_piloto_check(args, par_id, harness, modelo, indice, prompt, verificar=None):
    run_id = f"PILOTO-{harness}-{indice}"
    run_dir = RUNS / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    workspace = preparar_workspace_piloto(run_dir / "workspace") if not args.dry_run else run_dir / "workspace"
    if not args.dry_run:
        workspace.mkdir(parents=True, exist_ok=True)
    home = preparar_home(run_id, harness, args.dry_run, modelo,
                         getattr(args, "gateway_url", None), getattr(args, "api_key", None))
    if not args.dry_run:
        (workspace / "prompt.txt").write_text(prompt, encoding="utf-8")

    adapter = obter_adapter(harness)
    comando = adapter.build_command(modelo)
    if verificar:
        comando = f"{comando}; {verificar}"
    resultado = executar_no_container(args, workspace, home, comando, run_dir)
    return run_dir, workspace, resultado


def rodar_piloto(args, versoes, tabela_modelos):
    """Roda as cinco verificacoes da secao 7.12 para os nove pares."""
    if not args.dry_run:
        RUNS.mkdir(exist_ok=True)
    resultados = []

    for harness in HARNESSES:
        adapter = obter_adapter(harness)
        for _, modelo_rotulo, modelo_id, provedor in _MODELOS_PILOTO:
            modelo = resolver_modelo(harness, provedor, modelo_id, tabela_modelos)
            par = f"{adapter.NOME} x {modelo_rotulo}"
            print(f"[piloto] {par} (modelo={modelo})")
            registro = {
                "par": par, "harness": harness, "modelo": modelo_rotulo,
                "provedor": provedor, "autentica": "nao", "le": "nao",
                "edita": "nao", "executa": "nao", "gera_logs": "nao",
                "situacao": "protocol_incompatible", "observacao": "", "tokens_piloto": "",
            }

            # 1. Consulta simples
            run_dir, _, res = _rodar_piloto_check(
                args, par, harness, modelo, "1",
                "Responda apenas com a palavra OK.")
            eventos, uso = _eventos_validos(run_dir)
            if not args.dry_run and res["returncode"] == 0 and eventos:
                registro["autentica"] = "sim"

            # 2. Leitura
            run_dir, _, res = _rodar_piloto_check(
                args, par, harness, modelo, "2",
                "Leia o arquivo README.md e responda com a primeira linha.")
            eventos, uso = _eventos_validos(run_dir)
            if not args.dry_run and eventos:
                registro["le"] = "sim"

            # 3. Edicao
            run_dir, workspace, res = _rodar_piloto_check(
                args, par, harness, modelo, "3",
                "Crie o arquivo saida.txt contendo exatamente a palavra PILOTO.")
            if not args.dry_run:
                alvo = workspace / "saida.txt"
                if alvo.exists() and "PILOTO" in alvo.read_text(encoding="utf-8", errors="replace"):
                    registro["edita"] = "sim"

            # 4. Execucao e autocorrecao
            run_dir, workspace, res = _rodar_piloto_check(
                args, par, harness, modelo, "4",
                "O arquivo test.mjs falha porque soma.mjs esta errado. "
                "Corrija soma.mjs e rode `node test.mjs` ate passar.",
                verificar="node test.mjs")
            if not args.dry_run and res["returncode"] == 0:
                registro["executa"] = "sim"

            # 5. Eventos e uso
            eventos, uso = _eventos_validos(run_dir)
            if not args.dry_run and eventos:
                registro["gera_logs"] = "sim"
                if uso:
                    partes = []
                    for campo in ("input_tokens", "output_tokens", "cached_tokens"):
                        if uso.get(campo) is not None:
                            partes.append(f"{campo}={uso[campo]}")
                    registro["tokens_piloto"] = " ".join(partes)

            if all(registro[campo] == "sim" for campo in ("autentica", "le", "edita", "executa", "gera_logs")):
                registro["situacao"] = "compativel"
            resultados.append(registro)

    if not args.dry_run:
        with PILOTO_CSV.open("w", encoding="utf-8", newline="") as f:
            campos = ["par", "harness", "modelo", "provedor", "autentica", "le",
                      "edita", "executa", "gera_logs", "situacao", "observacao", "tokens_piloto"]
            w = csv.DictWriter(f, fieldnames=campos)
            w.writeheader()
            w.writerows(resultados)
        print(f"piloto gravado em {PILOTO_CSV}")
    else:
        print("[dry-run] piloto nao executado")

    compativeis = sum(1 for r in resultados if r["situacao"] == "compativel")
    print(f"pares compativeis: {compativeis}/{len(resultados)}")


_MODELOS_PILOTO = [
    ("GPT-6 Luna", "LUNA", "gpt-6-luna", "openai"),
    ("Claude Haiku 5.5", "HAIKU", "claude-haiku-5-5", "anthropic"),
    ("DeepSeek V4.1 Flash", "DEEPSEEK", "deepseek-v4.1-flash", "relace"),
]


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def montar_parser():
    p = argparse.ArgumentParser(description="Orquestrador de rodadas do TCC de harnesses")
    p.add_argument("--etapa", type=int, help="executar apenas uma etapa da fila")
    p.add_argument("--run-id", help="executar apenas uma rodada")
    p.add_argument("--limit", type=int, help="limitar o numero de rodadas")
    p.add_argument("--pilot", action="store_true", help="rodar o piloto de compatibilidade")
    p.add_argument("--force", action="store_true", help="refazer rodadas ja concluidas")
    p.add_argument("--dry-run", action="store_true", help="mostrar comandos sem executar")
    p.add_argument("--image", default="tcc-harnesses:v1")
    p.add_argument("--network", default="rede-experimento")
    p.add_argument("--time-limit", type=int, default=1200, help="limite em segundos por rodada")
    p.add_argument("--iteration-limit", type=int, default=None)
    p.add_argument("--cost-limit", type=float, default=None, help="limite em USD por rodada")
    p.add_argument("--gateway", default="9router", help="rotulo do roteador (manifest)")
    p.add_argument("--gateway-host", default=None, help="IP do gateway; padrao: gateway da rede")
    p.add_argument("--gateway-port", type=int, default=20128)
    p.add_argument("--api-key-file", default="~/.tcc-segredos/9router.key")
    p.add_argument("--no-gateway", action="store_true", help="nao injetar base URL/chave do roteador")
    p.add_argument("--router-version", default="9router")
    p.add_argument("--runtime-version", default="Node 22.23.3")
    p.add_argument("--browser-version", default=None)
    return p


def main():
    args = montar_parser().parse_args()
    args.gateway_url = detectar_gateway(args)
    args.api_key = ler_chave(args)
    if args.gateway_url:
        print(f"gateway: {args.gateway_url} (chave: {'ok' if args.api_key else 'ausente'})")
    versoes = ler_versoes()
    tabela_modelos = carregar_modelos()
    if args.pilot:
        rodar_piloto(args, versoes, tabela_modelos)
    else:
        rodar_fila(args, versoes, tabela_modelos)


if __name__ == "__main__":
    main()
