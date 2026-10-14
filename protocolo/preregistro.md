# Pré-registro

Decisões congeladas antes da Etapa 1 (plano v2, seção 7.8). Registro de 12/10/2026. Nenhuma rodada oficial foi executada. Depois do congelamento (`git tag congelamento-v1`), nada deste arquivo é alterado; mudanças posteriores entram em `checkpoints.md` como desvio.

> Legenda: **FATO** = confirmado por observação direta. **DECISÃO** = tomada pela pesquisadora. **PROPOSTA** = precisa de confirmação do orientador antes do congelamento.

| Item | Valor | Data | Justificativa |
|---|---|---|---|
| Slug GPT-6 Luna no OpenRouter | `openai/gpt-6-luna` (no 9router: `openrouter/openai/gpt-6-luna`) | 12/10/2026 | FATO: confirmado em `/v1/models` e em `usageHistory`. A variante Pro não é usada |
| Slug Claude Haiku 5.5 no OpenRouter | `anthropic/claude-haiku-5.5` (ID Anthropic: `claude-haiku-5-5`) | 12/10/2026 | FATO: idem. O ponto no slug importa para ler o custo no 9router |
| Slug DeepSeek V4.1 Flash no OpenRouter | `deepseek/deepseek-v4.1-flash` | 12/10/2026 | FATO: idem (servido pela Relace) |
| Provedores | GPT-6 Luna: `openai` · Haiku 5.5: `anthropic` · DeepSeek V4.1 Flash: `relace` | 12/10/2026 | FATO: o provedor oficial do DeepSeek está inativo na plataforma. Fixado no OpenRouter em duas camadas (Privacy → Allowed Providers; Model & Provider Access → Allowed Providers e Allowed Models). Prova por chamada: `scripts/verificar_provedor.py` |
| Versões de Node, Bun, browser e harnesses | Node 22.23.3 (imagem; o do host, 20.20.2, não é usado) · Bun: não usado · Playwright 1.64.0 / Chromium 1248 · Claude Code 2.1.197 · Codex 0.160.0 · OpenCode 1.18.34 · roteador 9router v0.5.95 | 12/10/2026 | FATO: ver `VERSOES.txt`. A imagem `tcc-harnesses:v1` (por id) é a fonte da verdade e não é reconstruída durante a coleta |
| Stack nos starters | Os três starters já trazem a stack do cenário (site: Vite + TypeScript; jogo: Vite + TypeScript + Canvas; app: React + TypeScript + Hono + SQLite), sem que o prompt precise dizê-la | 12/10/2026 | DECISÃO (plano 7.4): P1, P2 e P3 ficam comparáveis |
| SQLite no app | `node:sqlite` (embutido no Node 22), em vez de `better-sqlite3` | 12/10/2026 | DECISÃO: evita compilação nativa no contêiner |
| Teto de tempo | 1200 s (20 min) por rodada, igual para todas as combinações | 12/10/2026 | DECISÃO: aplicado pelo runner (`--time-limit 1200`); ao estourar, o contêiner é encerrado e o desfecho é `timeout` |
| Teto de custo | US$ 2,00 por rodada, igual para todas as combinações | 12/10/2026 | DECISÃO: aplicado pelo runner (`--cost-limit 2.0`): um vigia lê o 9router a cada 15 s e encerra o contêiner; o desfecho é `timeout` com `notes=cost_limit`, nunca sucesso |
| Limite de iterações | Não aplicado | 12/10/2026 | DECISÃO: os limites da rodada são tempo e custo; harnesses diferentes contam iterações de formas diferentes |
| Recursos do contêiner do agente | 2 CPUs, 4 GB de memória, 512 processos, `--cap-drop ALL`, `no-new-privileges`, usuário não-root | 12/10/2026 | DECISÃO: iguais para todas as rodadas; registrados no manifesto |
| Limiar de sucesso autônomo (seção 8.3) | Build aprovado E qualidade de referência (B) >= 50 | 12/10/2026 | DECISÃO: limiar conservador, a rever se a distribuição observada for muito baixa |
| Pesos dos critérios (seção 8.1) | Pesos propostos do plano (site 33, jogo 37, app 45), todos os critérios ativos | 12/10/2026 | DECISÃO (`avaliacao/*/pesos.json`). PROPOSTA: revisão com o orientador, que o plano pede |
| Mapeamento critério × prompt | `avaliacao/mapeamento-criterio-prompt.json` | 12/10/2026 | DECISÃO. PROPOSTA: revisão dos 4 pontos em aberto do próprio arquivo com o orientador |
| Critério não observado | Fica `null`, sai do denominador nas notas "observadas" (B e A). As notas "conservadoras" (nulo = 0) e a contagem de critérios não observados são sempre gravadas; a taxa de nulos por célula harness × modelo é reportada | 12/10/2026 | PROPOSTA mínima: confirmar com o orientador. Jogo (estado em `window`) e app (rotas descobertas) podem produzir nulos |
| Política de nova tentativa | 1 nova tentativa (até 2 execuções) para `provider_error` e `harness_error`, preservando a tentativa original (`summary.attemptN.json`); NÃO se aplica a `timeout` | 12/10/2026 | DECISÃO |
| Plano A ou B (seção 7.12) | A definir depois do piloto refeito (todos os 9 pares passando mantém o desenho completo) | 12/10/2026 | O piloto anterior não é auditável e foi descartado; ver `MANUAL-RODADAS.md` seção 2 |
| Política de rede do npm | O registro npm é liberado SOMENTE no preparo (`npm ci`), antes do isolamento; o agente roda sem internet | 12/10/2026 | DECISÃO: igual para todos; `runner.py` (`preparar_dependencias`) |
| Contrato do app (critérios A02–A10) | Híbrido: fluxos pela interface; semântica de backend (401/403/409) e concorrência pela descoberta das rotas que a própria aplicação usa, sem fixar rotas no prompt | 12/10/2026 | DECISÃO. PROPOSTA: ratificação pelo orientador (`avaliacao/METODOLOGIA.md`) |
| Parâmetros de inferência (7.10 item 7) | Temperatura 0 onde o harness permitir (OpenCode); esforço de raciocínio registrado pelo valor EFETIVO (`reasoning_tokens` do 9router); limitações do Claude Code e do Codex documentadas | 12/10/2026 | DECISÃO |
| Onde roda o avaliador | Contêiner `tcc-harnesses:v1`, repositório montado somente leitura e só a pasta da rodada gravável, cache de browsers montado | 12/10/2026 | DECISÃO: `app` exige `node:sqlite` (Node 22); mantém o avaliador separado do agente |
| Testes unitários e análise estática | Vitest e ESLint não são usados; a verificação de regras e estados é feita por E2E (Playwright) e a estática é o `tsc --noEmit` do build | 12/10/2026 | DECISÃO: ver `avaliacao/METODOLOGIA.md` (testes por importação direta dependeriam de nomes internos que o prompt não exige) |
| Pré-voo | Obrigatório antes de cada rodada (`orchestrator/preflight.py`); referência em `protocolo/congelamento.json` | 12/10/2026 | DECISÃO (plano 7.10): se qualquer item reprovar, a rodada não começa |
| Margem de segurança da projeção entre etapas | 20% | 12/10/2026 | DECISÃO |
| Sorteio da fila | `random.Random(20261009).shuffle` dentro de cada etapa de 27 execuções | 12/10/2026 | DECISÃO: mesma semente do guia; algoritmo diferente (o do guia é xorshift em JavaScript) e ordem estratificada por etapa |
| Orçamento | Saldo experimental oficial a registrar quando o ambiente estiver pronto (previsto: US$ 20,00) | 12/10/2026 | DECISÃO |
