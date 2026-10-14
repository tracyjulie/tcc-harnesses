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
import copy
import csv
import hashlib
import json
import re
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import normalizer  # noqa: E402
import preflight  # noqa: E402
import router_logs  # noqa: E402
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
    "run_id", "etapa", "scenario", "harness", "model_label", "prompt_level",
    "repetition", "attempt", "provider", "provider_effective", "provider_mismatch",
    "tipo_integracao", "gateway", "runtime_status", "artefato_modificado", "avaliado",
    "duration_seconds", "input_tokens", "output_tokens", "cached_tokens",
    "reasoning_tokens", "cost_usd", "cost_method", "tool_calls",
    "build_success", "tests_passed", "tests_total", "criterios_nao_observados",
    "reference_quality", "reference_quality_conservadora",
    "prompt_adherence", "prompt_adherence_conservadora", "notes",
]

CAMPOS_FILA = ["ordem", "etapa", "condicional", "run_id", "cenario", "harness",
               "modelo_rotulo", "modelo_id", "provedor", "prompt", "repeticao", "status"]

CAMPOS_PILOTO = ["par", "harness", "modelo", "provedor", "tipo_integracao", "autentica",
                 "le", "edita", "executa", "gera_logs", "situacao", "modelo_efetivo",
                 "provedor_efetivo", "endpoint", "observacao", "tokens_piloto", "evidencia"]

# Padrao de classificacao de falhas (so e consultado quando o codigo de saida != 0).
PADRAO_CREDITO = re.compile(
    r"insufficient[ _](credits?|quota|funds)|payment required|out of credits|"
    r"credits?[ _](balance[ _])?(is[ _])?(too[ _]low|exhausted)|\b402\b", re.I)
PADRAO_PROVEDOR = re.compile(
    r"rate.?limit|too many requests|\b(429|500|502|503|504|529)\b|overloaded|"
    r"service unavailable|bad gateway|gateway timeout|api error|"
    r"econnrefused|econnreset|etimedout|enotfound|connection (refused|reset)", re.I)

# Limites de recursos do conteiner do agente (registrados no manifesto).
PADRAO_CPUS = "2"
PADRAO_MEMORIA = "4g"
PADRAO_PIDS = "512"


def tipo_integracao(harness, provedor):
    """Classificacao da rota (plano 7.9 e 7.12) usada na analise de sensibilidade."""
    if harness == "opencode":
        return "rota_esperada"
    if harness == "codex":
        return "rota_esperada" if provedor == "openai" else "gateway"
    if harness == "claude-code":
        return "rota_esperada" if provedor == "anthropic" else "sem_suporte_oficial"
    return None


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


IGNORAR_NA_ARVORE = ("node_modules", "dist", ".git", "prompt.txt")


def sha256_arvore(raiz, ignorar=()):
    h = hashlib.sha256()
    for arquivo in sorted(p for p in raiz.rglob("*") if p.is_file()):
        rel = arquivo.relative_to(raiz)
        if any(parte in ignorar for parte in rel.parts):
            continue
        h.update(str(rel).encode("utf-8"))
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
    with FILA.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS_FILA, lineterminator="\n")
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


def _celula(valor):
    """Valores compostos (dict/lista) vao para o CSV como JSON; None fica vazio."""
    if isinstance(valor, (dict, list)):
        return json.dumps(valor, ensure_ascii=False, sort_keys=True)
    return valor


def registrar_resultado(resumo):
    linhas = []
    if RESULTADOS.exists() and RESULTADOS.stat().st_size:
        with RESULTADOS.open("r", encoding="utf-8", newline="") as f:
            linhas = list(csv.DictReader(f))
    linhas = [l for l in linhas if l.get("run_id") != resumo["run_id"]]
    linha = {campo: _celula(resumo.get(campo)) for campo in CAMPOS_RESULTADOS}
    linhas.append(linha)
    with RESULTADOS.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS_RESULTADOS, lineterminator="\n",
                           extrasaction="ignore")
        w.writeheader()
        w.writerows(linhas)


def redigir_chave(raiz, chave):
    """Troca a chave do roteador por *** nos arquivos de texto da rodada.

    O agente recebe a chave por variavel de ambiente e pode imprimi-la. Isso
    evita que ela va parar em events.jsonl, stderr.log, snapshot ou home.
    Devolve o numero de arquivos alterados.
    """
    if not chave or not raiz.exists():
        return 0
    alterados = 0
    alvo = chave.encode("utf-8")
    for caminho in raiz.rglob("*"):
        if not caminho.is_file() or caminho.stat().st_size > 20 * 1024 * 1024:
            continue
        try:
            dados = caminho.read_bytes()
        except OSError:
            continue
        if alvo in dados:
            caminho.write_bytes(dados.replace(alvo, b"***"))
            alterados += 1
    return alterados


def info_imagem(args):
    """Id da imagem e versoes lidas de DENTRO do conteiner (consulta unica, em cache)."""
    if getattr(args, "_info_imagem", None) is not None:
        return args._info_imagem
    info = {"image_id": None, "versoes": {}}
    if not getattr(args, "dry_run", False):
        try:
            info["image_id"] = subprocess.run(
                ["docker", "image", "inspect", "--format", "{{.Id}}", args.image],
                capture_output=True, text=True, check=True, timeout=30).stdout.strip() or None
            saida = subprocess.run(
                ["docker", "run", "--rm", args.image, "bash", "-lc",
                 "node --version; claude --version; codex --version; opencode --version"],
                capture_output=True, text=True, timeout=180).stdout.splitlines()
            info["versoes"] = dict(zip(["node", "claude-code", "codex", "opencode"],
                                       [l.strip() for l in saida]))
        except Exception:  # noqa: BLE001
            pass
    args._info_imagem = info
    return info


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
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns(".git", "dist", "node_modules"))
    return dst


def preparar_dependencias(workspace, args, run_dir):
    """Instala as dependencias do starter num passo com rede.

    O agente roda em rede isolada e nao instala pacotes; as dependencias vem do
    `package-lock.json`, instaladas aqui com o Node da imagem (passo separado,
    antes do isolamento). Pular com --npm-deps skip.
    """
    if args.dry_run or args.npm_deps == "skip":
        return
    if (workspace / "node_modules").exists():
        return
    comando = "npm ci" if args.npm_deps == "ci" else "npm install --no-audit --no-fund"
    with (run_dir / "deps.log").open("wb") as saida:
        subprocess.run(
            ["docker", "run", "--rm",
             "-v", f"{workspace}:/w", "-w", "/w",
             args.image, "bash", "-lc", comando],
            stdout=saida, stderr=subprocess.STDOUT, check=False,
        )


def preparar_home(run_id, harness, dry_run=False, modelo=None, gateway_url=None, api_key=None):
    home = RUNS / run_id / "home"
    if home.exists():
        shutil.rmtree(home)  # HOME sempre novo: nada de sessoes de tentativas anteriores
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
            # Equalizacao dos parametros de inferencia (plano 7.10 item 7):
            # temperatura 0 e explicitada para o agente de build. O valor
            # efetivo de raciocinio e lido dos logs do 9router (reasoning_tokens).
            "agent": {"build": {"temperature": 0}},
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


def repo_sujo():
    """True se ha alteracoes nao commitadas fora de dados/ e runs/."""
    try:
        saida = subprocess.run(["git", "-C", str(RAIZ), "status", "--porcelain"],
                               capture_output=True, text=True, check=True).stdout
    except Exception:  # noqa: BLE001
        return None
    for linha in saida.splitlines():
        caminho = linha[3:].strip().strip('"')
        if not (caminho.startswith("dados/") or caminho.startswith("runs/")):
            return True
    return False


def gravar_manifest(run_id, linha, workspace, prompt_path, args, versoes):
    lock = FIXTURES / f"{linha['cenario']}-base" / "package-lock.json"
    info = info_imagem(args)
    harness_ver = info["versoes"].get(linha["harness"]) or versao_harness(versoes, linha["harness"])
    manifest = {
        "run_id": run_id,
        "scenario": linha["cenario"],
        "harness": linha["harness"],
        "model_label": linha["modelo_rotulo"],
        "model_id": linha["modelo_id"],
        "provider": linha["provedor"],
        "tipo_integracao": tipo_integracao(linha["harness"], linha["provedor"]),
        "gateway": args.gateway,
        "started_at_utc": agora_utc(),
        "harness_version": harness_ver,
        "harness_version_fonte": "lida do conteiner" if info["versoes"].get(linha["harness"]) else "VERSOES.txt",
        "router_version": args.router_version,
        "runtime_version": info["versoes"].get("node") or args.runtime_version,
        "browser_version": args.browser_version,
        "image": args.image,
        "image_id": info["image_id"],
        "scenario_commit_sha": git_head(),
        "repo_sujo": repo_sujo(),
        "scenario_lockfile_sha256": sha256_arquivo(lock),
        "prompt_sha256": sha256_arquivo(prompt_path),
        "time_limit_seconds": args.time_limit,
        "cost_limit_usd": args.cost_limit,
        "iteration_limit": None,
        "iteration_limit_nota": "nao aplicado: os limites da rodada sao tempo e custo",
        "container_limits": {"cpus": args.cpus, "memory": args.memory, "pids": args.pids_limit,
                             "cap_drop": "ALL", "no_new_privileges": True},
        "network_policy": f"isolado ({args.network}); saida apenas para o roteador",
        "npm_deps": args.npm_deps,
        "inference_params": {
            "temperature": 0 if linha["harness"] == "opencode" else None,
            "temperature_aplicada_por": "opencode.json (agent.build)" if linha["harness"] == "opencode" else None,
            "reasoning_effort": None,
            "observacao": "temperatura 0 fixada onde o harness permite (OpenCode); "
                          "raciocinio efetivo registrado por reasoning_tokens do 9router",
        },
    }
    caminho = RUNS / run_id / "manifest.json"
    if not args.dry_run:
        caminho.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


# --------------------------------------------------------------------------- #
# Execucao no container
# --------------------------------------------------------------------------- #
def nome_conteiner(run_dir):
    """Nome fixo do conteiner da rodada (permite mata-lo no timeout)."""
    return "tcc-" + re.sub(r"[^A-Za-z0-9_.-]", "-", run_dir.name)


def montar_docker(args, workspace, home, comando, nome=None):
    cmd = ["docker", "run", "--rm", "--network", args.network]
    if nome:
        cmd += ["--name", nome]
    # Limites de recursos e endurecimento (guia secao 06; plano 7.10 item 1).
    cmd += ["--cpus", str(args.cpus), "--memory", str(args.memory),
            "--pids-limit", str(args.pids_limit),
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges"]
    cmd += [
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


def _matar_conteiner(nome):
    """Para o conteiner da rodada. `docker kill` e o unico jeito de encerrar o agente:
    matar so o cliente `docker run` deixa o conteiner vivo, gastando credito."""
    try:
        subprocess.run(["docker", "kill", nome], capture_output=True, timeout=60)
    except Exception:  # noqa: BLE001
        pass


def executar_no_container(args, workspace, home, comando, run_dir, cost_watch=None):
    """Executa o harness no conteiner e devolve {returncode, timed_out, duration_seconds, limit_reason}.

    - O conteiner tem nome fixo e e MORTO (`docker kill`) ao estourar o tempo.
    - Se `cost_watch` for dado ({inicio, provedor, modelo_id, limite}), um vigia consulta
      o 9router a cada `args.cost_poll` segundos e mata o conteiner ao atingir o teto
      de custo; o desfecho vira `timeout` com motivo `cost_limit`.
    """
    events = run_dir / "events.jsonl"
    stderr = run_dir / "stderr.log"
    nome = nome_conteiner(run_dir)
    if args.dry_run:
        print("  [dry-run] docker " + " ".join(montar_docker(args, workspace, home, comando, nome)[1:]))
        return {"returncode": None, "timed_out": False, "duration_seconds": None, "limit_reason": None}

    subprocess.run(["docker", "rm", "-f", nome], capture_output=True)  # nome livre
    inicio = time.monotonic()
    timed_out = False
    limit_reason = None
    returncode = None
    parar = threading.Event()
    estado = {"motivo": None}

    def vigiar():
        while not parar.wait(args.cost_poll):
            custo = router_logs.custo_desde(cost_watch["inicio"], cost_watch["provedor"],
                                            cost_watch["modelo_id"])
            if custo is not None and custo >= cost_watch["limite"]:
                estado["motivo"] = "cost_limit"
                _matar_conteiner(nome)
                return

    with events.open("wb") as fo, stderr.open("wb") as fe:
        proc = subprocess.Popen(montar_docker(args, workspace, home, comando, nome),
                                stdout=fo, stderr=fe)
        if cost_watch and cost_watch.get("limite"):
            threading.Thread(target=vigiar, daemon=True).start()
        try:
            returncode = proc.wait(timeout=args.time_limit)
        except subprocess.TimeoutExpired:
            timed_out = True
            _matar_conteiner(nome)
            try:
                proc.wait(timeout=60)
            except subprocess.TimeoutExpired:
                proc.kill()
        except BaseException:
            _matar_conteiner(nome)
            proc.kill()
            raise
        finally:
            parar.set()
    limit_reason = estado["motivo"]
    duracao = round(time.monotonic() - inicio, 3)
    return {"returncode": returncode if not timed_out else None, "timed_out": timed_out,
            "duration_seconds": duracao, "limit_reason": limit_reason}


def classificar_status(res, stderr_texto, eventos_texto=""):
    """Classifica o desfecho da rodada (plano 7.14a).

    So olha o texto de erro quando o codigo de saida e diferente de 0: um
    stderr com a palavra 'provider' num cabecalho de uma rodada bem-sucedida
    nao pode virar provider_error.
    """
    if res.get("limit_reason"):
        return "timeout", res["limit_reason"]
    if res.get("timed_out"):
        return "timeout", "time_limit"
    if res.get("returncode") == 0:
        return "completed", None
    texto = f"{stderr_texto or ''}\n{eventos_texto or ''}"
    if PADRAO_CREDITO.search(texto):
        return "aborted", "credit_exhausted"
    if PADRAO_PROVEDOR.search(texto):
        return "provider_error", None
    return "harness_error", None


# --------------------------------------------------------------------------- #
# Avaliacao independente
# --------------------------------------------------------------------------- #
def rodar_avaliador(run_id, cenario, prompt_level, args):
    """Roda o avaliador independente sobre o snapshot congelado.

    Por padrao o avaliador roda em um conteiner a partir da imagem do
    experimento (Node 22, necessario para o cenario `app`, que usa
    `node:sqlite`). O repositorio e montado SOMENTE LEITURA; apenas a pasta da
    propria rodada e gravavel (o codigo gerado pelo agente roda aqui e nao pode
    alterar testes nem outras rodadas). Com `--evaluator host` roda no host.
    Campos nao observados ficam `null`.
    """
    run_dir = RUNS / run_id
    campos = {
        "avaliado": True,
        "build_success": None, "tests_passed": None, "tests_total": None,
        "criterios_nao_observados": None,
        "reference_quality": None, "reference_quality_conservadora": None,
        "prompt_adherence": None, "prompt_adherence_conservadora": None,
    }
    test_results = run_dir / "test-results.json"

    avaliador = AVALIACAO / "avaliar.py"
    if avaliador.exists():
        try:
            if getattr(args, "evaluator", "container") == "container":
                cache = Path.home() / ".cache" / "ms-playwright"
                cmd = [
                    "docker", "run", "--rm", "--name", f"tcc-aval-{run_id}",
                    "-v", f"{RAIZ}:/repo:ro",
                    "-v", f"{run_dir}:/repo/runs/{run_id}",
                    "-e", "PLAYWRIGHT_BROWSERS_PATH=/evalcache",
                    "-w", "/repo",
                ]
                if cache.exists():
                    cmd += ["-v", f"{cache}:/evalcache:ro"]
                cmd += [
                    args.image, "python3", "/repo/avaliacao/avaliar.py",
                    f"/repo/runs/{run_id}/source-snapshot", cenario,
                    f"/repo/runs/{run_id}",
                ]
            else:
                cmd = [
                    sys.executable, str(avaliador),
                    str(run_dir / "source-snapshot"), cenario, str(run_dir),
                ]
            subprocess.run(cmd, capture_output=True, text=True,
                           timeout=3600, check=False)
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
        campos["reference_quality_conservadora"] = soma.get("referencia_B", {}).get(
            "conservadora_nulos_como_zero")
        campos["criterios_nao_observados"] = soma.get("referencia_B", {}).get("nao_observados")
        campos["prompt_adherence"] = soma.get("aderencia_A", {}).get("observada")
        campos["prompt_adherence_conservadora"] = soma.get("aderencia_A", {}).get(
            "conservadora_nulos_como_zero")
        dados = json.loads(test_results.read_text(encoding="utf-8"))
        criterios = dados.get("criterios", [])
        campos["tests_total"] = len(criterios)
        campos["tests_passed"] = sum(1 for c in criterios if c.get("passou") == 1)

    mapa_build = {"site": "S01", "jogo": "J01", "app": "A01"}
    parte_build = run_dir / "avaliacao-resultados" / f"{mapa_build[cenario]}_build.json"
    if parte_build.exists():
        try:
            campos["build_success"] = bool(
                json.loads(parte_build.read_text(encoding="utf-8")).get("passou"))
        except (json.JSONDecodeError, OSError):
            campos["build_success"] = None
    return campos


# --------------------------------------------------------------------------- #
# Processamento de uma rodada
# --------------------------------------------------------------------------- #
class PreflightFalhou(Exception):
    """O pre-voo reprovou: a rodada NAO e executada (nenhum credito e gasto)."""


def processar_linha(linha, args, versoes, tabela_modelos):
    run_id = linha["run_id"]
    run_dir = RUNS / run_id
    resumo_previo = run_dir / "summary.json"
    tentativa_atual = 1
    if resumo_previo.exists():
        if not args.force:
            print(f"[pular] {run_id} (summary.json ja existe; use --force para refazer)")
            return
        # Nova tentativa: preserva o registro da tentativa original
        # (plano 7.8, politica de retry).
        tentativa = 1
        while (run_dir / f"summary.attempt{tentativa}.json").exists():
            tentativa += 1
        resumo_previo.replace(run_dir / f"summary.attempt{tentativa}.json")
        tentativa_atual = tentativa + 1

    run_dir.mkdir(parents=True, exist_ok=True)
    prompt_origem = PROMPTS / f"{linha['cenario']}-p{linha['prompt']}.txt"
    if not prompt_origem.exists():
        print(f"[erro] prompt ausente: {prompt_origem}")
        return

    modelo = resolver_modelo(linha["harness"], linha["provedor"], linha["modelo_id"], tabela_modelos)
    workspace = preparar_workspace(run_id, linha["cenario"], args.dry_run)
    preparar_dependencias(workspace, args, run_dir)
    home = preparar_home(run_id, linha["harness"], args.dry_run, modelo,
                         getattr(args, "gateway_url", None), getattr(args, "api_key", None))

    prompt_txt = run_dir / "prompt.txt"
    if not args.dry_run:
        shutil.copy(prompt_origem, prompt_txt)
        shutil.copy(prompt_origem, workspace / "prompt.txt")

    # Pre-voo (plano 7.10): se qualquer item reprovar, a rodada nao comeca.
    if not args.dry_run and not args.skip_preflight:
        resultados = preflight.verificar(args, linha, workspace, home, prompt_origem,
                                         modelo, info_imagem(args))
        (run_dir / "preflight.json").write_text(
            json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")
        reprovados = [r for r in resultados if not r["ok"]]
        if reprovados:
            for r in reprovados:
                print(f"  [preflight] FALHOU: {r['item']}: {r['detalhe']}")
            raise PreflightFalhou(run_id)

    manifest = gravar_manifest(run_id, linha, workspace, prompt_origem, args, versoes)

    adapter = obter_adapter(linha["harness"])
    comando = adapter.build_command(modelo)

    cost_watch = None
    if args.cost_limit:
        cost_watch = {"inicio": manifest["started_at_utc"], "provedor": linha["provedor"],
                      "modelo_id": linha["modelo_id"], "limite": args.cost_limit}

    print(f"[rodar] {run_id}: {adapter.NOME} / {modelo} / P{linha['prompt']}")
    resultado = executar_no_container(args, workspace, home, comando, run_dir, cost_watch)
    if args.dry_run:
        return
    fim_agente = agora_utc()  # fim do AGENTE (antes do avaliador)

    # Congelar a solucao (sem o prompt.txt, que nao faz parte do artefato).
    (workspace / "prompt.txt").unlink(missing_ok=True)
    snapshot = run_dir / "source-snapshot"
    if snapshot.exists():
        shutil.rmtree(snapshot)
    shutil.copytree(workspace, snapshot,
                    ignore=shutil.ignore_patterns("node_modules", "dist"))

    # A chave do roteador esta no ambiente do agente: nao pode ficar nos artefatos.
    chave = getattr(args, "api_key", None)
    redacoes = redigir_chave(snapshot, chave) + redigir_chave(home, chave)
    redacoes += _redigir_arquivo(run_dir / "events.jsonl", chave)
    redacoes += _redigir_arquivo(run_dir / "stderr.log", chave)
    (run_dir / "source-snapshot.sha256").write_text(sha256_arvore(snapshot), encoding="utf-8")

    stderr_texto = ""
    if (run_dir / "stderr.log").exists():
        stderr_texto = (run_dir / "stderr.log").read_text(encoding="utf-8", errors="replace")
    eventos_texto = ""
    if (run_dir / "events.jsonl").exists():
        eventos_texto = (run_dir / "events.jsonl").read_text(
            encoding="utf-8", errors="replace")[-20000:]
    runtime_status, motivo = classificar_status(resultado, stderr_texto, eventos_texto)

    agregado = normalizer.normalizar_run(run_dir)

    # So se mede qualidade de codigo quando HA artefato: o agente terminou/estourou
    # o limite, ou o snapshot difere do starter. Falha de integracao sem artefato
    # nao e evidencia de qualidade (plano 7.14) e nao pode virar nota.
    starter = FIXTURES / f"{linha['cenario']}-base"
    artefato_modificado = (sha256_arvore(snapshot, IGNORAR_NA_ARVORE)
                           != sha256_arvore(starter, IGNORAR_NA_ARVORE))
    if runtime_status in ("completed", "timeout") or artefato_modificado:
        qualidade = rodar_avaliador(run_id, linha["cenario"], linha["prompt"], args)
    else:
        qualidade = {c: None for c in (
            "build_success", "tests_passed", "tests_total", "criterios_nao_observados",
            "reference_quality", "reference_quality_conservadora",
            "prompt_adherence", "prompt_adherence_conservadora")}
        qualidade["avaliado"] = False

    # Custo e uso efetivos pelo ponto unico de instrumentacao (9router).
    uso_router = router_logs.agregar_janela(
        manifest["started_at_utc"], fim_agente, linha["provedor"], linha["modelo_id"])

    def _preferir(router_valor, evento_valor):
        return router_valor if router_valor is not None else evento_valor

    if uso_router["cost_usd"] is not None:
        cost_method = uso_router["cost_method"]
    elif agregado["cost_usd"] is not None:
        cost_method = "estimado pelo harness (eventos)"
    else:
        cost_method = None

    efetivo = uso_router.get("provedor_efetivo")
    esperado_rotulo = router_logs.PROVEDOR_ROTULO.get(linha["provedor"], linha["provedor"])
    mismatch = None if not efetivo else any(k.lower() != esperado_rotulo.lower() for k in efetivo)
    endpoints = uso_router["router_endpoints"]
    endpoint_usado = max(endpoints, key=endpoints.get) if endpoints else None

    notas = [n for n in (motivo,
                         f"chave_redigida_em_{redacoes}_arquivos" if redacoes else None) if n]
    resumo = {
        "run_id": run_id,
        "etapa": int(linha["etapa"]),
        "scenario": linha["cenario"],
        "harness": linha["harness"],
        "model_label": linha["modelo_rotulo"],
        "model_id": linha["modelo_id"],
        "provider": linha["provedor"],
        "provider_effective": efetivo,
        "provider_mismatch": mismatch,
        "tipo_integracao": manifest["tipo_integracao"],
        "endpoint_usado": endpoint_usado,
        "gateway": args.gateway,
        "prompt_level": int(linha["prompt"]),
        "repetition": int(linha["repeticao"]),
        "attempt": tentativa_atual,
        "started_at_utc": manifest["started_at_utc"],
        "finished_at_utc": fim_agente,
        "scenario_commit_sha": manifest["scenario_commit_sha"],
        "harness_version": manifest["harness_version"],
        "prompt_sha256": manifest["prompt_sha256"],
        "runtime_status": runtime_status,
        "artefato_modificado": artefato_modificado,
        "avaliado": qualidade["avaliado"] if "avaliado" in qualidade else True,
        "duration_seconds": resultado["duration_seconds"],
        "input_tokens": _preferir(uso_router["input_tokens"], agregado["input_tokens"]),
        "output_tokens": _preferir(uso_router["output_tokens"], agregado["output_tokens"]),
        "cached_tokens": _preferir(uso_router["cached_tokens"], agregado["cached_tokens"]),
        "reasoning_tokens": uso_router["reasoning_tokens"],
        "cost_usd": _preferir(uso_router["cost_usd"], agregado["cost_usd"]),
        "cost_method": cost_method,
        "router_requests": uso_router["router_requests"],
        "router_endpoints": endpoints,
        "provider_models_vistos": uso_router["router_models"],
        "tool_calls": agregado["tool_calls"],
        "test_executions_by_agent": agregado["test_executions_by_agent"],
        "verified_self_corrections": None,
        "manual_interventions": 0,
        "build_success": qualidade["build_success"],
        "tests_passed": qualidade["tests_passed"],
        "tests_total": qualidade["tests_total"],
        "criterios_nao_observados": qualidade["criterios_nao_observados"],
        "reference_quality": qualidade["reference_quality"],
        "reference_quality_conservadora": qualidade["reference_quality_conservadora"],
        "prompt_adherence": qualidade["prompt_adherence"],
        "prompt_adherence_conservadora": qualidade["prompt_adherence_conservadora"],
        "notes": "; ".join(notas) if notas else None,
        "exit_code": resultado["returncode"],
        "events_lidos": agregado["eventos_lidos"],
        "linhas_invalidas": agregado["linhas_invalidas"],
    }
    (run_dir / "summary.json").write_text(
        json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")

    registrar_resultado(resumo)
    marcar_status_fila(run_id, runtime_status)
    print(f"  status={runtime_status} duracao={resultado['duration_seconds']}s "
          f"tool_calls={agregado['tool_calls']} avaliado={resumo['avaliado']}")


def _redigir_arquivo(caminho, chave):
    """Versao de `redigir_chave` para um unico arquivo."""
    if not chave or not caminho.exists():
        return 0
    dados = caminho.read_bytes()
    alvo = chave.encode("utf-8")
    if alvo in dados:
        caminho.write_bytes(dados.replace(alvo, b"***"))
        return 1
    return 0


# --------------------------------------------------------------------------- #
# Fila principal
# --------------------------------------------------------------------------- #
def selecionar_linhas(args):
    linhas = ler_fila()
    if args.run_id:
        linhas = [l for l in linhas if l["run_id"] == args.run_id]
    if args.etapa:
        linhas = [l for l in linhas if int(l["etapa"]) == args.etapa]
    if not args.force and not args.run_id:
        # Sem --force, roda apenas as rodadas ainda nao executadas. Rodadas
        # com desfecho retentavel sao refeitas com --force (politica de retry).
        linhas = [l for l in linhas if l["status"] == "planejada"]
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
        except PreflightFalhou as e:
            print(f"[parado] pre-voo reprovou em {e}. Nada foi executado nem gasto. "
                  f"Corrija o item apontado e rode de novo.")
            return
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


EVIDENCIAS_PILOTO = RAIZ / "protocolo" / "evidencias" / "piloto"


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


def _texto_eventos(run_dir):
    caminho = run_dir / "events.jsonl"
    return caminho.read_text(encoding="utf-8", errors="replace") if caminho.exists() else ""


def _rodar_piloto_check(args, harness, modelo_rotulo, modelo, indice, prompt, verificar=None):
    """Uma verificacao do piloto. O id inclui o MODELO: cada par guarda a sua evidencia."""
    run_id = f"PILOTO-{harness}-{modelo_rotulo}-{indice}"
    run_dir = RUNS / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    workspace = run_dir / "workspace"
    if not args.dry_run:
        preparar_workspace_piloto(workspace)
    home = preparar_home(run_id, harness, args.dry_run, modelo,
                         getattr(args, "gateway_url", None), getattr(args, "api_key", None))
    if not args.dry_run:
        (workspace / "prompt.txt").write_text(prompt, encoding="utf-8")

    comando = obter_adapter(harness).build_command(modelo)
    if verificar:
        comando = f"{comando}; {verificar}"
    args_check = copy.copy(args)
    args_check.time_limit = min(args.time_limit, 300)  # tarefas minimas
    inicio = agora_utc()
    resultado = executar_no_container(args_check, workspace, home, comando, run_dir)
    fim = agora_utc()
    if not args.dry_run:
        chave = getattr(args, "api_key", None)
        _redigir_arquivo(run_dir / "events.jsonl", chave)
        _redigir_arquivo(run_dir / "stderr.log", chave)
        redigir_chave(home, chave)
        # evidencia preservada fora de runs/ (que e ignorado pelo Git)
        destino = EVIDENCIAS_PILOTO / run_id
        destino.mkdir(parents=True, exist_ok=True)
        for nome in ("events.jsonl", "stderr.log"):
            if (run_dir / nome).exists():
                shutil.copy(run_dir / nome, destino / nome)
        for nome in ("saida.txt", "soma.mjs"):
            if (workspace / nome).exists():
                shutil.copy(workspace / nome, destino / nome)
    return run_dir, workspace, resultado, inicio, fim


def rodar_piloto(args, versoes, tabela_modelos):
    """Roda as cinco verificacoes da secao 7.12 para os nove pares.

    Criterios (todos exigem EVIDENCIA, nao so ausencia de erro):
      1 consulta : saida 0, a resposta 'OK' nos eventos e uso do modelo-alvo no 9router
      2 leitura  : o conteudo do README ('Projeto piloto') aparece nos eventos
      3 edicao   : saida.txt contem exatamente PILOTO
      4 execucao : o agente rodou `node test.mjs`, corrigiu soma.mjs e o teste passa
      5 logs     : eventos, tokens (9router) e chamadas de ferramenta reconhecidas (> 0)
    """
    if not args.dry_run:
        RUNS.mkdir(exist_ok=True)
    resultados = []

    harnesses = [args.pilot_harness] if args.pilot_harness else HARNESSES
    for harness in harnesses:
        adapter = obter_adapter(harness)
        for _, modelo_rotulo, modelo_id, provedor in _MODELOS_PILOTO:
            if args.pilot_model and args.pilot_model.lower() not in (modelo_id.lower(), modelo_rotulo.lower()):
                continue
            modelo = resolver_modelo(harness, provedor, modelo_id, tabela_modelos)
            par = f"{adapter.NOME} x {modelo_rotulo}"
            print(f"[piloto] {par} (modelo={modelo})")
            registro = {
                "par": par, "harness": harness, "modelo": modelo_rotulo,
                "provedor": provedor, "tipo_integracao": tipo_integracao(harness, provedor),
                "autentica": "nao", "le": "nao", "edita": "nao", "executa": "nao",
                "gera_logs": "nao", "situacao": "protocol_incompatible",
                "modelo_efetivo": "", "provedor_efetivo": "", "endpoint": "",
                "observacao": "", "tokens_piloto": "",
                "evidencia": f"protocolo/evidencias/piloto/PILOTO-{harness}-{modelo_rotulo}-*",
            }
            motivos = []

            # 1. Consulta simples
            run_dir, _, res, ini, fim = _rodar_piloto_check(
                args, harness, modelo_rotulo, modelo, "1",
                "Responda apenas com a palavra OK.")
            eventos, _uso = _eventos_validos(run_dir)
            uso = router_logs.agregar_janela(ini, fim, provedor, modelo_id) if not args.dry_run else {}
            if not args.dry_run:
                usou_alvo = bool(uso.get("router_requests")) and uso.get("input_tokens") is not None
                if res["returncode"] == 0 and eventos and "OK" in _texto_eventos(run_dir) and usou_alvo:
                    registro["autentica"] = "sim"
                else:
                    motivos.append("consulta: sem saida 0, sem 'OK' nos eventos ou sem uso do modelo-alvo no 9router")
                modelos_vistos = uso.get("router_models") or {}
                registro["modelo_efetivo"] = uso.get("modelo_esperado") if usou_alvo else ""
                if len(modelos_vistos) > 1:
                    motivos.append(f"outros modelos vistos na janela: {sorted(m for m in modelos_vistos if m != uso.get('modelo_esperado'))}")
                if uso.get("provedor_efetivo"):
                    registro["provedor_efetivo"] = json.dumps(uso["provedor_efetivo"], sort_keys=True)
                if uso.get("router_endpoints"):
                    registro["endpoint"] = max(uso["router_endpoints"], key=uso["router_endpoints"].get)

            # 2. Leitura (o conteudo do README so aparece se a ferramenta de leitura rodou)
            run_dir, _, res, ini, fim = _rodar_piloto_check(
                args, harness, modelo_rotulo, modelo, "2",
                "Leia o arquivo README.md e responda com a primeira linha.")
            if not args.dry_run:
                if "Projeto piloto" in _texto_eventos(run_dir):
                    registro["le"] = "sim"
                else:
                    motivos.append("leitura: conteudo do README nao aparece nos eventos")

            # 3. Edicao (conteudo exato)
            run_dir, workspace, res, ini, fim = _rodar_piloto_check(
                args, harness, modelo_rotulo, modelo, "3",
                "Crie o arquivo saida.txt contendo exatamente a palavra PILOTO.")
            if not args.dry_run:
                alvo = workspace / "saida.txt"
                if alvo.exists() and alvo.read_text(encoding="utf-8", errors="replace").strip() == "PILOTO":
                    registro["edita"] = "sim"
                else:
                    motivos.append("edicao: saida.txt ausente ou diferente de PILOTO")

            # 4. Execucao e autocorrecao
            run_dir, workspace, res, ini, fim = _rodar_piloto_check(
                args, harness, modelo_rotulo, modelo, "4",
                "O arquivo test.mjs falha porque soma.mjs esta errado. "
                "Corrija soma.mjs e rode `node test.mjs` ate passar.",
                verificar="node test.mjs")
            if not args.dry_run:
                agente_rodou = "node test.mjs" in _texto_eventos(run_dir)
                corrigiu = (workspace / "soma.mjs").exists() and "a + b" in (workspace / "soma.mjs").read_text(
                    encoding="utf-8", errors="replace")
                if res["returncode"] == 0 and agente_rodou and corrigiu:
                    registro["executa"] = "sim"
                else:
                    motivos.append("execucao: teste nao passou, soma.mjs nao foi corrigido ou o agente nao rodou `node test.mjs`")

            # 5. Eventos e uso
            if not args.dry_run:
                agregado = normalizer.normalizar_run(run_dir)
                uso4 = router_logs.agregar_janela(ini, fim, provedor, modelo_id)
                eventos, uso_ev = _eventos_validos(run_dir)
                partes = []
                for campo in ("input_tokens", "output_tokens", "cached_tokens"):
                    v = uso4.get(campo) if uso4.get(campo) is not None else (uso_ev or {}).get(campo)
                    if v is not None:
                        partes.append(f"{campo}={v}")
                registro["tokens_piloto"] = " ".join(partes)
                if eventos and uso4.get("input_tokens") is not None and (agregado["tool_calls"] or 0) > 0:
                    registro["gera_logs"] = "sim"
                else:
                    motivos.append(
                        f"logs: eventos={eventos}, tokens_router={uso4.get('input_tokens')}, "
                        f"tool_calls_reconhecidas={agregado['tool_calls']} (parser pode nao reconhecer o formato)")

            if all(registro[c] == "sim" for c in ("autentica", "le", "edita", "executa", "gera_logs")):
                registro["situacao"] = "compativel"
            registro["observacao"] = " | ".join(motivos)
            resultados.append(registro)

    if not args.dry_run:
        with PILOTO_CSV.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=CAMPOS_PILOTO, lineterminator="\n")
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
    p.add_argument("--pilot-harness", default=None, help="piloto: apenas um harness")
    p.add_argument("--pilot-model", default=None, help="piloto: apenas um modelo (id ou rotulo)")
    p.add_argument("--force", action="store_true", help="refazer rodadas ja concluidas")
    p.add_argument("--dry-run", action="store_true", help="mostrar comandos sem executar")
    p.add_argument("--image", default="tcc-harnesses:v1")
    p.add_argument("--network", default="rede-experimento")
    p.add_argument("--time-limit", type=int, default=1200, help="limite em segundos por rodada")
    p.add_argument("--npm-deps", choices=["ci", "install", "skip"], default="ci",
                   help="preparo das dependencias do starter antes da rodada (rede)")
    p.add_argument("--cost-limit", type=float, default=2.0,
                   help="teto de custo em USD por rodada (preregistro: 2.0); 0 desliga o vigia")
    p.add_argument("--cost-poll", type=int, default=15,
                   help="segundos entre as consultas do vigia de custo ao 9router")
    p.add_argument("--cpus", default=PADRAO_CPUS, help="CPUs do conteiner do agente")
    p.add_argument("--memory", default=PADRAO_MEMORIA, help="memoria do conteiner do agente")
    p.add_argument("--pids-limit", default=PADRAO_PIDS, help="maximo de processos no conteiner")
    p.add_argument("--skip-preflight", action="store_true",
                   help="so para diagnostico: NAO use na coleta oficial")
    p.add_argument("--gateway", default="9router", help="rotulo do roteador (manifest)")
    p.add_argument("--gateway-host", default=None, help="IP do gateway; padrao: gateway da rede")
    p.add_argument("--gateway-port", type=int,
                   default=int(__import__("os").environ.get("TCC_GATEWAY_PORT", 20128)),
                   help="porta do gateway alcancavel pelo agente (padrao 20128; com proxy, 20129)")
    p.add_argument("--api-key-file", default="~/.tcc-segredos/9router.key")
    p.add_argument("--no-gateway", action="store_true", help="nao injetar base URL/chave do roteador")
    p.add_argument("--router-version", default="9router v0.5.95")
    p.add_argument("--runtime-version", default="Node 22.23.3")
    p.add_argument("--browser-version", default="Playwright 1.64.0 / Chromium 1248")
    p.add_argument("--evaluator", choices=["container", "host"], default="container",
                   help="onde roda o avaliador (container Node 22 por padrao)")
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
