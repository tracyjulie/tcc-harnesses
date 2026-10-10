"""Adaptador do OpenCode (plano v2, secao 6.1).

Execucao nao interativa: `opencode run --format json`.
O prompt e lido de `prompt.txt` no diretorio de trabalho.
"""

NOME = "OpenCode"


def build_command(model):
    """Comando executado dentro do container, com cwd no workspace."""
    return f'opencode run --model "{model}" --format json "$(cat prompt.txt)"'
