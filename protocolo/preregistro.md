# Pre-registro

Decisoes congeladas antes da etapa 1 (plano v2, secao 7.8). Preencher e datar cada item. Depois de preenchido, nao alterar; mudancas posteriores entram em `checkpoints.md` como desvio.

> Legenda: linhas com **FATO** foram confirmadas por observacao direta. Linhas em branco sao **DECISOES** que a pesquisadora precisa tomar (nao foram preenchidas para nao inventar valores).

| Item | Valor | Data | Justificativa |
|---|---|---|---|
| Slug GPT-6 Luna no OpenRouter | `openai/gpt-6-luna` (via 9router: `openrouter/openai/gpt-6-luna`) | 10/10/2026 | FATO: confirmado em `http://127.0.0.1:20128/v1/models` |
| Slug Claude Haiku 5.5 no OpenRouter | `anthropic/claude-haiku-5.5` | 10/10/2026 | FATO: idem |
| Slug DeepSeek V4.1 Flash no OpenRouter | `deepseek/deepseek-v4.1-flash` | 10/10/2026 | FATO: idem (servido pela Relace) |
| Provedor GPT-6 Luna | `openai` | 10/10/2026 | FATO: fixado na conta OpenRouter |
| Provedor Claude Haiku 5.5 | `anthropic` | 10/10/2026 | FATO: fixado na conta OpenRouter |
| Provedor DeepSeek V4.1 Flash | `relace` | 10/10/2026 | FATO: provedor oficial DeepSeek inativo na plataforma |
| Versoes de Node, Bun e browser de teste | Node 22.23.3 (imagem); Bun: nao usado; Chromium 156 / Playwright 1.64.0 | 10/10/2026 | FATO: verificadas na imagem e no servidor |
| Teto de tempo por cenario | | | DECISAO |
| Teto de custo por cenario | | | DECISAO |
| Limiar de sucesso autonomo (secao 8.3) | | | DECISAO (sugerir com o orientador) |
| Pesos dos criterios (secao 8.1) | | | DECISAO: `avaliacao/*/pesos.json` hoje e proposta |
| Politica de nova tentativa (provider_error, harness_error) | | | DECISAO |
| Plano A ou B (secao 7.12) | Nenhum: desenho completo (9/9 pares compativeis) | 10/10/2026 | FATO: piloto de compatibilidade |
| Politica de rede do npm para os starters | | | DECISAO |
| Mapeamento criterio x prompt | | | DECISAO: `avaliacao/mapeamento-criterio-prompt.json` hoje e rascunho |
