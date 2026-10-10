"""Adaptador do Codex (plano v2, secao 6.1).

Execucao nao interativa: `codex exec --json`.
Provedores personalizados usam o protocolo Responses API; o 9router precisa
expor `/v1/responses`. O prompt entra por stdin a partir de `prompt.txt`.
"""

NOME = "Codex"


def build_command(model):
    """Comando executado dentro do container, com cwd no workspace.

    `--skip-git-repo-check` porque o workspace nao carrega historico git.
    `--dangerously-bypass-approvals-and-sandbox` da autonomia equivalente aos
    demais harnesses; o isolamento real e o proprio container (secao 7.10).
    """
    return (
        f'codex exec --json --model "{model}" '
        f'--skip-git-repo-check --dangerously-bypass-approvals-and-sandbox '
        f'- < prompt.txt'
    )
