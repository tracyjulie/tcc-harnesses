"""Adaptador do Claude Code (plano v2, secao 6.1).

Execucao nao interativa: `claude -p --output-format stream-json`.
`--tools` define o conjunto de ferramentas exposto (sem ferramentas de busca
web); `--dangerously-skip-permissions` libera o regime autonomo. Nao ha
suporte oficial da Anthropic a modelos nao Claude por essa via, o que sera
tratado no piloto de compatibilidade (secao 7.12).
"""

NOME = "Claude Code"

FERRAMENTAS = "Read,Write,Edit,Bash,Glob,Grep,TodoWrite"


def build_command(model):
    """Comando executado dentro do container, com cwd no workspace."""
    return (
        f'claude -p "$(cat prompt.txt)" --model "{model}" '
        f'--tools "{FERRAMENTAS}" '
        f'--dangerously-skip-permissions --output-format stream-json'
    )
