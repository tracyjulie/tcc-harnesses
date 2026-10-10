=== Claude Code ===
claude -p "PROMPT" --tools "Read,Write,Edit,Bash,Glob,Grep,TodoWrite" --dangerously-skip-permissions

=== Codex ===
codex exec "SEU_PROMPT_AQUI"

mkdir -p ~/.codex
cat > ~/.codex/config.toml << 'EOF'
[tools]
web_search = false
EOF

=== OpenCode ===
cat > opencode.json << 'EOF'
{
  "$schema": "https://opencode.ai/config.json",
  "tools": {
    "webfetch": false
  },
  "websearch": false
}
EOF

=== Configuracao de cada harness no ambiente isolado ===
Claude Code
  Restricao de ferramentas: --tools define quais ferramentas internas existem para o modelo; --allowedTools apenas pre-aprova e nao as remove.
  Comando: claude -p "PROMPT" --tools "Read,Write,Edit,Bash,Glob,Grep,TodoWrite" --dangerously-skip-permissions

OpenCode
  Arquivo de configuracao no HOME da rodada (OPENCODE_CONFIG=/home/executor/opencode.json), fora do workspace, para que o diretorio de trabalho comece vazio.
  Permissoes: edit=allow, bash=allow, webfetch=deny. Temperatura 0 e limite de passos definidos em agent.build.

Codex
  Protocolo: wire_api="responses" (versoes atuais nao aceitam "chat"); o 9router precisa expor /v1/responses.

=== Flags confirmadas com --help (10/10/2026, imagem tcc-harnesses:v1) ===
Claude Code 2.1.197: -p/--print, --model, --tools <tools...>, --output-format stream-json,
  --dangerously-skip-permissions, --allowedTools/--disallowedTools.
Codex 0.160.0: exec, --json (JSONL), -m/--model, -s/--sandbox, -C/--cd,
  --skip-git-repo-check, --dangerously-bypass-approvals-and-sandbox.
OpenCode 1.18.34: run, -m/--model (provider/model), --format json, --auto,
  -c/--continue, -s/--session, --pure, --agent.

Comandos efetivos usados pelo orquestrador (orchestrator/adapters/):
  claude -p "$(cat prompt.txt)" --model "M" --tools "Read,Write,Edit,Bash,Glob,Grep,TodoWrite" --dangerously-skip-permissions --output-format stream-json
  codex exec --json --model "M" --skip-git-repo-check --dangerously-bypass-approvals-and-sandbox - < prompt.txt
  opencode run --model "P/M" --format json --auto "$(cat prompt.txt)"

Nota: a autonomia foi equalizada (Claude --dangerously-skip-permissions, Codex bypass, OpenCode --auto), conforme a secao 7.10 item 5. O workspace nao tem .git, por isso o --skip-git-repo-check no Codex.
