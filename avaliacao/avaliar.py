#!/usr/bin/env python3
"""Avaliador independente (plano v2, secoes 8.1 e 11).

Roda sobre o snapshot congelado de uma rodada, fora do alcance do agente:
1. instala dependencias do starter e roda o build;
2. sobe o servidor do cenario;
3. roda as suites Playwright, que registram um JSON por criterio;
4. agrega os criterios em `test-results.json`.

Uso:
    python avaliacao/avaliar.py <snapshot> <site|jogo|app> <run_dir>

Campos nao observados ficam `null` (nunca zero). Se o servidor nao subir,
os criterios comportamentais permanecem `null` e os dados brutos sao
preservados em `run_dir/avaliacao-resultados/`.
"""

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
AVALIACAO = RAIZ / "avaliacao"
PORTA_PADRAO = 4317
BASE_URL = f"http://127.0.0.1:{PORTA_PADRAO}"

CENARIOS = {
    "site": "S01",
    "jogo": "J01",
    "app": "A01",
}


def npm():
    return "npm.cmd" if os.name == "nt" else "npm"


def npx():
    return "npx.cmd" if os.name == "nt" else "npx"


def node():
    return "node.exe" if os.name == "nt" else "node"


def executar(comando, cwd, log, timeout=1800, env=None):
    ambiente = dict(os.environ)
    if env:
        ambiente.update(env)
    with log.open("ab") as f:
        f.write(f"\n$ {' '.join(str(c) for c in comando)} (cwd={cwd})\n".encode())
        f.flush()
        return subprocess.run(
            comando, cwd=str(cwd), stdout=f, stderr=subprocess.STDOUT,
            timeout=timeout, env=ambiente, check=False,
        ).returncode


def registrar_parcial(results_dir, cenario, sufixo, passou, motivo):
    ident = f"{CENARIOS[cenario]}_{sufixo}"
    (results_dir / f"{ident}.json").write_text(
        json.dumps({"id": ident, "passou": passou, "motivo": motivo}, ensure_ascii=False),
        encoding="utf-8",
    )


def instalar_dependencias(snapshot, log):
    if (snapshot / "node_modules").exists():
        return True
    if executar([npm(), "ci"], snapshot, log, timeout=1200) == 0:
        return True
    return executar([npm(), "install", "--no-audit", "--no-fund"], snapshot, log, timeout=1200) == 0


def build(snapshot, log):
    if not instalar_dependencias(snapshot, log):
        return False
    return executar([npm(), "run", "build"], snapshot, log, timeout=1800) == 0


def subir_servidor(snapshot, cenario, log):
    if cenario in ("site", "jogo"):
        comando = [npm(), "run", "dev", "--", "--port", str(PORTA_PADRAO), "--host", "127.0.0.1"]
    else:
        contrato = AVALIACAO / "app" / "contrato.json"
        if contrato.exists():
            dados = json.loads(contrato.read_text(encoding="utf-8"))
            comando = dados.get("start_cmd")
        else:
            comando = None
        if not comando:
            comando = [npm(), "run", "dev"]
    with log.open("ab") as f:
        f.write(f"\n$ {' '.join(comando)} (servidor)\n".encode())
        return subprocess.Popen(
            comando, cwd=str(snapshot), stdout=f, stderr=subprocess.STDOUT,
            env={**os.environ, "PORT": str(PORTA_PADRAO)},
        )


def esperar_servidor(url, segundos=60):
    limite = time.time() + segundos
    while time.time() < limite:
        try:
            with urllib.request.urlopen(url, timeout=2) as resposta:
                if resposta.status < 500:
                    return True
        except Exception:  # noqa: BLE001
            time.sleep(1.5)
    return False


def rodar_playwright(cenario, log, results_dir):
    ambiente = {
        "APP_URL": BASE_URL,
        "RESULTS_DIR": str(results_dir),
        "PW_REPORT": str(results_dir.parent / "playwright-report.json"),
    }
    return executar([npx(), "playwright", "test"], AVALIACAO / cenario, log,
                    timeout=1800, env=ambiente)


def agregar(cenario, log, results_dir, destino):
    rc = executar([node(), "shared/collect.mjs", cenario], AVALIACAO, log,
                  timeout=300, env={"RESULTS_DIR": str(results_dir)})
    origem = results_dir / "test-results.json"
    if origem.exists():
        shutil.copy(origem, destino)
        return True
    return False


def main():
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    snapshot = Path(sys.argv[1]).resolve()
    cenario = sys.argv[2]
    run_dir = Path(sys.argv[3]).resolve()
    if cenario not in CENARIOS:
        sys.exit(f"cenario invalido: {cenario}")

    run_dir.mkdir(parents=True, exist_ok=True)
    results_dir = run_dir / "avaliacao-resultados"
    results_dir.mkdir(parents=True, exist_ok=True)
    log = run_dir / "avaliacao.log"
    destino = run_dir / "test-results.json"

    # O snapshot congelado e evidencia e nao pode ser alterado: o build e os
    # testes rodam sobre uma copia.
    area = run_dir / "avaliacao-build"
    if area.exists():
        shutil.rmtree(area)
    shutil.copytree(snapshot, area,
                    ignore=shutil.ignore_patterns("node_modules", "dist", ".git"),
                    dirs_exist_ok=True)

    servidor = None
    try:
        ok_build = build(area, log)
        registrar_parcial(results_dir, cenario, "build",
                          True if ok_build else False,
                          "build aprovado" if ok_build else "build reprovado (ver avaliacao.log)")

        servidor = subir_servidor(area, cenario, log)
        if esperar_servidor(BASE_URL):
            rodar_playwright(cenario, log, results_dir)
        else:
            print("servidor nao respondeu; criterios comportamentais ficam null")
    except Exception as e:  # noqa: BLE001
        print(f"avaliador falhou: {e}")
    finally:
        if servidor is not None:
            servidor.terminate()
            try:
                servidor.wait(timeout=15)
            except Exception:  # noqa: BLE001
                servidor.kill()

    if agregar(cenario, log, results_dir, destino):
        print(f"test-results.json gravado em {destino}")
    else:
        print("agregacao nao produziu test-results.json")


if __name__ == "__main__":
    main()
