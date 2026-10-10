# Desenho experimental

Resumo operacional (detalhamento no plano v2). Congelado em 10/10/2026.

- **Delineamento:** fatorial 3 harnesses × 3 modelos × 3 cenários × 3 prompts
  = 81 condições; até 2 repetições = 162 execuções (`dados/plano_162_execucoes.csv`).
- **Harnesses:** OpenCode 1.18.34, Codex 0.160.0, Claude Code 2.1.197.
- **Modelos:** GPT-6 Luna (`openai/gpt-6-luna`), Claude Haiku 5.5
  (`anthropic/claude-haiku-5.5`), DeepSeek V4.1 Flash via Relace
  (`deepseek/deepseek-v4.1-flash`).
- **Cenários:** TecnoIF 2026 (site, baixa), Labirinto Explorer (jogo, média),
  ReservaFácil (app, alta).
- **Prompts:** P1 resumido, P2 intermediário, P3 detalhado (Apêndice A do plano).
- **Ordem:** etapas por complexidade crescente, sorteio com semente `20261009`
  dentro de cada etapa; verificação de orçamento entre etapas.
- **Ambiente:** contêiner isolado, home descartável, rede isolada só com o
  roteador; dependências por `npm ci` antes do isolamento.
- **Instrumentação:** 9router (`~/.9router/db/data.sqlite`) fornece custo,
  tokens, cache e reasoning por chamada.
- **Métricas:** qualidade de referência (B) e aderência (A), separadas; build,
  tempo, custo, autonomia; sem índice composto.
- **Decisões:** ver `preregistro.md`. **Metodologia do avaliador:** ver
  `avaliacao/METODOLOGIA.md`.
