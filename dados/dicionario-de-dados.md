# Dicionário de dados

Campos de `runs/<run_id>/summary.json` (esquema do §11 do plano) e de
`dados/resultados.csv`. Campo não observado é `null`, nunca `0`.

| Campo | Tipo | Descrição |
|---|---|---|
| run_id | string | Identificador `CENARIO-HARNESS-MODELO-PROMPT-RR` |
| scenario | string | `site` · `jogo` · `app` |
| harness | string | `opencode` · `codex` · `claude-code` |
| model_label | string | `LUNA` · `HAIKU` · `DEEPSEEK` |
| model_id | string | slug do modelo |
| provider | string | provedor fixado (`openai` · `anthropic` · `relace`) |
| gateway | string | rótulo do roteador (`9router`) |
| prompt_level | int | 1 · 2 · 3 |
| repetition | int | 1 (R1) · 2 (R2) |
| started_at_utc / finished_at_utc | string | horários UTC |
| scenario_commit_sha | string | commit-base do starter |
| harness_version | string | versão do harness |
| prompt_sha256 | string | hash do prompt |
| runtime_status | string | `completed`/`timeout`/`provider_error`/`harness_error`/`protocol_incompatible`/`aborted` |
| duration_seconds | float | duração do processo do harness |
| input_tokens / output_tokens / cached_tokens / reasoning_tokens | int | tokens efetivos (9router; fallback eventos) |
| cost_usd | float | custo medido (USD) |
| cost_method | string | `medido (usageHistory do 9router)` · `estimado pelo harness (eventos)` · null |
| router_requests | int | nº de chamadas do 9router na janela da rodada |
| router_endpoints | objeto | contagem por endpoint |
| provider_models_vistos | objeto | contagem por modelo (detecta contaminação) |
| tool_calls | int | chamadas de ferramenta (eventos normalizados) |
| test_executions_by_agent | int | execuções de teste pelo próprio agente |
| verified_self_corrections | int/null | autocorreções verificadas |
| manual_interventions | int | sempre 0 (sem intervenção) |
| build_success | bool/null | build do snapshot |
| tests_passed / tests_total | int | contagem de critérios aprovados/total |
| reference_quality | float/null | indicador B (0-100) |
| prompt_adherence | float/null | indicador A (0-100) |
| notes | string/null | motivo (ex.: `credit_exhausted`) |
| exit_code | int/null | código de saída do harness |
| events_lidos / linhas_invalidas | int | estatística do normalizador |

`manifest.json` contém ainda `inference_params` (temperature/reasoning) e os
limites de tempo/custo.
