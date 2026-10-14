# Dicionário de dados

Campos de `runs/<run_id>/summary.json` e colunas de `dados/resultados.csv` (registro de 12/10/2026). Campo não observado é `null` (célula vazia no CSV), nunca `0`. Campos compostos (objetos) vão como JSON no CSV.

## Identificação
| Campo | Tipo | Descrição |
|---|---|---|
| run_id | string | `CENARIO-HARNESS-MODELO-PROMPT-RR` |
| etapa | int | 1 a 6 (ver `MANUAL-RODADAS.md` §3) |
| scenario | string | `site` · `jogo` · `app` |
| harness | string | `opencode` · `codex` · `claude-code` |
| model_label | string | `LUNA` · `HAIKU` · `DEEPSEEK` |
| model_id | string | ID do modelo no plano |
| prompt_level | int | 1 · 2 · 3 |
| repetition | int | 1 (R1) · 2 (R2) |
| attempt | int | 1 = primeira execução; 2 = nova tentativa (política de retry) |

## Rota
| Campo | Tipo | Descrição |
|---|---|---|
| provider | string | provedor fixado: `openai` · `anthropic` · `relace` |
| provider_effective | objeto/null | provedor que de fato respondeu, lido de `requestDetails` do 9router (ex.: `{"Relace": 12}`); `null` se não disponível |
| provider_mismatch | bool/null | `true` se algum provedor efetivo difere do fixado |
| tipo_integracao | string | `rota_esperada` · `gateway` · `sem_suporte_oficial` (plano 7.9) |
| endpoint_usado | string | endpoint mais usado no 9router (`/v1/chat/completions`, `/v1/responses` ou `/v1/messages`) |
| gateway | string | rótulo do roteador (`9router`) |

## Execução
| Campo | Tipo | Descrição |
|---|---|---|
| started_at_utc / finished_at_utc | string | início e fim do AGENTE (UTC; o fim não inclui o avaliador) |
| runtime_status | string | `completed` · `timeout` · `provider_error` · `harness_error` · `protocol_incompatible` · `aborted` |
| duration_seconds | float | duração do processo do harness |
| exit_code | int/null | código de saída do harness |
| notes | string/null | motivo (`time_limit`, `cost_limit`, `credit_exhausted`, `chave_redigida_em_N_arquivos`) |
| manual_interventions | int | sempre 0 |

## Consumo
| Campo | Tipo | Descrição |
|---|---|---|
| input_tokens / output_tokens / cached_tokens / reasoning_tokens | int | tokens efetivos (9router; fallback: eventos) |
| cost_usd | float | custo medido (USD) |
| cost_method | string | `medido (usageHistory do 9router)` · `estimado pelo harness (eventos)` · null |
| router_requests | int | nº de chamadas do 9router na janela da rodada |
| router_endpoints | objeto | contagem por endpoint |
| provider_models_vistos | objeto | contagem por modelo na janela (mais de um modelo indica contaminação) |
| tool_calls | int | chamadas de ferramenta reconhecidas pelo normalizador |
| test_executions_by_agent | int | execuções de teste feitas pelo próprio agente |
| verified_self_corrections | null | não calculado automaticamente (extrair na análise de `normalizados.jsonl`) |

## Qualidade
| Campo | Tipo | Descrição |
|---|---|---|
| artefato_modificado | bool | o snapshot difere do starter |
| avaliado | bool | o avaliador rodou (só roda com artefato) |
| build_success | bool/null | build do snapshot |
| tests_passed / tests_total | int | critérios aprovados / total de critérios (10 por cenário; não observado conta como não aprovado) |
| criterios_nao_observados | int | critérios sem observação (`null`) |
| reference_quality | float/null | indicador B (0–100), critérios observados |
| reference_quality_conservadora | float/null | B com não observado = 0 |
| prompt_adherence | float/null | indicador A (0–100), critérios observados |
| prompt_adherence_conservadora | float/null | A com não observado = 0 |

`manifest.json` traz ainda `image_id`, as versões lidas do contêiner, `container_limits`, `cost_limit_usd`, `repo_sujo` e `inference_params`. `preflight.json` traz o resultado de cada item do pré-voo.
