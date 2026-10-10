# Pre-registro

Decisoes congeladas antes da etapa 1 (plano v2, secao 7.8). Preencher e datar cada item. Depois de preenchido, nao alterar; mudancas posteriores entram em `checkpoints.md` como desvio.

> Legenda: linhas com **FATO** foram confirmadas por observacao direta. Linhas com **DECISAO** foram tomadas pela pesquisadora (10/10/2026) e estao congeladas.
>
> As decisoes abaixo foram adotadas apos revisao do handoff (`documentacao/PROXIMOS-PASSOS.md`) e do guia do orientador (`guia_tcc_harnesses_prof_ricardo.html`). Qualquer revisao futura deve ser registrada como desvio em `checkpoints.md`.

| Item | Valor | Data | Justificativa |
|---|---|---|---|
| Slug GPT-6 Luna no OpenRouter | `openai/gpt-6-luna` (via 9router: `openrouter/openai/gpt-6-luna`) | 10/10/2026 | FATO: confirmado em `http://127.0.0.1:20128/v1/models`; variante Pro descartada |
| Slug Claude Haiku 5.5 no OpenRouter | `anthropic/claude-haiku-5.5` | 10/10/2026 | FATO: idem |
| Slug DeepSeek V4.1 Flash no OpenRouter | `deepseek/deepseek-v4.1-flash` | 10/10/2026 | FATO: idem (servido pela Relace) |
| Provedor GPT-6 Luna | `openai` | 10/10/2026 | FATO: fixado na conta OpenRouter |
| Provedor Claude Haiku 5.5 | `anthropic` | 10/10/2026 | FATO: fixado na conta OpenRouter |
| Provedor DeepSeek V4.1 Flash | `relace` | 10/10/2026 | FATO: provedor oficial DeepSeek inativo na plataforma |
| Versoes de Node, Bun e browser de teste | Node 22.23.3 (imagem; host 20 nao usado p/ avaliar); Bun: nao usado; Playwright 1.64.0 / Chromium 1248 | 10/10/2026 | DECISAO+FATO: ver `VERSOES.txt` |
| Teto de tempo por cenario | 1200 s (20 min) por rodada, igual para todas as combinacoes | 10/10/2026 | DECISAO: sugestao do plano (secao 7.8); `--time-limit 1200` |
| Teto de custo por cenario | US$ 2,00 por rodada, igual para todas as combinacoes | 10/10/2026 | DECISAO: sugestao do handoff; registrado por rodada |
| Limiar de sucesso autonomo (secao 8.3) | Build aprovado E qualidade de referencia (B) >= 50 | 10/10/2026 | DECISAO: limiar propositalmente conservador, a rever se a distribuicao observada for muito baixa |
| Pesos dos criterios (secao 8.1) | Aprovados os pesos propostos do plano (site 33, jogo 37, app 45 pontos de peso) | 10/10/2026 | DECISAO: `avaliacao/*/pesos.json`, com TODOS os criterios ativados |
| Politica de nova tentativa (provider_error, harness_error) | 1 nova tentativa (ate 2 execucoes), preservando o registro da tentativa original; NAO se aplica a `timeout` | 10/10/2026 | DECISAO |
| Plano A ou B (secao 7.12) | Nenhum: desenho completo (9/9 pares compativeis) | 10/10/2026 | FATO: piloto de compatibilidade |
| Politica de rede do npm para os starters | Liberar o registro npm SOMENTE no passo de preparo de dependencias (`npm ci`), antes do isolamento; o agente roda em rede isolada, sem internet | 10/10/2026 | DECISAO: igual para todos; implementado em `runner.py` (`preparar_dependencias`) |
| Mapeamento criterio x prompt | Aprovado `avaliacao/mapeamento-criterio-prompt.json` (apos ativacao de todos os criterios) | 10/10/2026 | DECISAO |
| Contrato do app (secao 7.10 / criterios A02-A10) | Hibrido: fluxos pela interface; semantica de backend (401/403/409) e concorrencia pela DESCOBERTA das rotas que a propria aplicacao usa (interceptacao de rede), sem fixar rotas no prompt | 10/10/2026 | DECISAO: o prompt nao fixa rotas; testar por contrato fixo puniria escolhas legitimas (plano 7.10 item 10 e guia secao 08) |
| Parametros de inferencia (secao 7.10 item 7) | Temperatura 0 onde o harness permitir; esforco de raciocinio registrado pelo valor EFETIVO (`reasoning_tokens` do 9router); limitacoes da Claude Code documentadas | 10/10/2026 | DECISAO |
| Onde roda o avaliador (P4) | Conteiner `tcc-harnesses:v1` (Node 22), repositorio e cache de browsers montados | 10/10/2026 | DECISAO: `app` exige `node:sqlite` (Node 22); mantem o avaliador separado do agente |
