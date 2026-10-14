#!/usr/bin/env python3
"""`docker` de mentira para testar o orquestrador sem Docker e sem gastar nada.

Imita so o necessario. Importante: `docker run` aqui se comporta como o de
verdade em UM ponto crucial: o "conteiner" e um processo separado, e matar o
CLIENTE (o que o subprocess faz no timeout) NAO mata o conteiner. So `docker
kill NOME` mata. O estado fica em $FAKE_DOCKER_STATE.
"""
import os, signal, subprocess, sys, time
from pathlib import Path

estado = Path(os.environ["FAKE_DOCKER_STATE"]); estado.mkdir(parents=True, exist_ok=True)
a = sys.argv[1:]

def vivos():
    out = []
    for f in estado.glob("*.pid"):
        pid = int(f.read_text())
        try:
            os.kill(pid, 0); out.append(f.stem)
        except OSError:
            f.unlink()
    return out

def matar(nome):
    f = estado / f"{nome}.pid"
    if f.exists():
        try:
            os.killpg(int(f.read_text()), signal.SIGKILL)
        except OSError:
            pass
        f.unlink()

if a[:1] == ["rm"]:
    matar(a[-1]); sys.exit(0)
if a[:1] == ["kill"]:
    matar(a[1]); print(a[1]); sys.exit(0)
if a[:1] == ["ps"]:
    for n in vivos():
        if "name=tcc-" in " ".join(a) and not n.startswith("tcc-"): continue
        print(n if "-q" in a else n)
    sys.exit(0)
if a[:2] == ["image", "inspect"]:
    print(os.environ.get("FAKE_IMAGE_ID", "sha256:imagemfalsa")); sys.exit(0)
if a[:2] == ["network", "inspect"]:
    print(os.environ.get("FAKE_NET_INTERNAL", "true") if "{{.Internal}}" in a else "172.18.0.1"); sys.exit(0)
if a[:1] == ["run"]:
    nome = a[a.index("--name") + 1] if "--name" in a else None
    cmd = a[-1]
    if "claude --version" in cmd:
        print("v22.23.3\n2.1.197 (Claude Code)\ncodex-cli 0.160.0\n1.18.34"); sys.exit(0)
    if "example.com" in cmd:
        sys.exit(0 if os.environ.get("FAKE_EGRESS_OK") else 6)
    if "avaliar.py" in " ".join(a):
        sys.exit(0)
    if "sleep" in cmd:
        # conteiner: processo proprio, em outro grupo; sobrevive a morte do cliente
        p = subprocess.Popen(["sleep", "600"], start_new_session=True)
        if nome:
            (estado / f"{nome}.pid").write_text(str(p.pid))
        p.wait(); sys.exit(0)
    sys.exit(int(os.environ.get("FAKE_RUN_RC", "0")))
sys.exit(0)
