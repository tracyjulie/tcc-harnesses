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
