# Configuração dos harnesses no ambiente isolado

Registro de 12/10/2026. Tudo abaixo corresponde ao que o código faz (`orchestrator/runner.py`, função `preparar_home`, e `orchestrator/adapters/`). Se mudar um, mude o outro.

## Comandos efetivos

```
claude -p "$(cat prompt.txt)" --model "M" --tools "Read,Write,Edit,Bash,Glob,Grep,TodoWrite" --verbose --dangerously-skip-permissions --output-format stream-json
codex exec --json --model "M" --skip-git-repo-check --dangerously-bypass-approvals-and-sandbox - < prompt.txt
opencode run --model "P/M" --format json --auto "$(cat prompt.txt)"
```

Flags confirmadas com `--help` nas versões congeladas (Claude Code 2.1.197, Codex 0.160.0, OpenCode 1.18.34).

## Equalização de autonomia (plano 7.10 item 5)

- Claude Code: `--dangerously-skip-permissions`. `--tools` define quais ferramentas existem para o modelo (sem busca web); `--allowedTools` só pré-aprova e não remove.
- Codex: `--dangerously-bypass-approvals-and-sandbox`. O isolamento real é o contêiner. `--skip-git-repo-check` porque o workspace não tem `.git`.
- OpenCode: `--auto`.

## Busca web desligada

- Claude Code: não há ferramenta de busca na lista de `--tools`.
- Codex: `[tools] web_search = false` em `~/.codex/config.toml` (HOME da rodada).
- OpenCode: `"tools": {"webfetch": false}` em `opencode.json` (apontado por `OPENCODE_CONFIG`, no HOME da rodada, fora do workspace).
- Em qualquer caso, o contêiner não tem saída para a internet.

## Provedor e protocolo

- OpenCode: provedor `9router` (`@ai-sdk/openai-compatible`), endpoint `/v1/chat/completions`, temperatura 0 em `agent.build`.
- Codex: `wire_api = "responses"` (versões atuais não aceitam `chat`); o 9router expõe `/v1/responses`.
- Claude Code: `ANTHROPIC_BASE_URL` apontando para o 9router, endpoint `/v1/messages`.
- Limite de passos: não aplicado. Os limites da rodada são tempo (1200 s) e custo (US$ 2,00).
