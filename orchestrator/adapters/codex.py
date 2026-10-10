"""Adaptador do Codex (plano v2, secao 6.1).

Execucao nao interativa: `codex exec --json`.
Provedores personalizados usam o protocolo Responses API; o 9router precisa
expor `/v1/responses`. O prompt entra por stdin a partir de `prompt.txt`.
"""

NOME = "Codex"


def build_command(model):
    """Comando executado dentro do container, com cwd no workspace."""
    return f'codex exec --json --model "{model}" - < prompt.txt'
