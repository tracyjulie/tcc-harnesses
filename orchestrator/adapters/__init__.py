"""Adaptadores por harness (plano v2, secao 11).

Cada adaptador sabe apenas montar o comando nao interativo do harness.
A captura de stdout/stderr, o codigo de saida e o estado da rodada ficam
a cargo do runner; a conversao dos eventos nativos fica a cargo do
normalizer. O identificador de modelo (`model`) e resolvido pelo runner.

Os comandos abaixo seguem `MANUAL-RODADAS.md` (secao 2) e `config-rede.md`.
As flags foram confirmadas com `--help` das versoes fixadas (ver `VERSOES.txt`);
reconfirme-as se a imagem for reconstruida.
"""

from . import claude_code, codex, opencode

ADAPTERS = {
    "opencode": opencode,
    "codex": codex,
    "claude-code": claude_code,
}

# Ordem estavel usada no piloto e nos relatorios.
HARNESSES = ["opencode", "codex", "claude-code"]


def obter(harness):
    """Devolve o modulo adaptador do harness, ou levanta KeyError."""
    if harness not in ADAPTERS:
        raise KeyError(f"harness desconhecido: {harness!r}")
    return ADAPTERS[harness]
