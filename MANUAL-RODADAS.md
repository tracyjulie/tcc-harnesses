# Manual de rodadas

Procedimento para o piloto e para a coleta definitiva, conforme o plano v2 (§7.8 a §7.14). Siga na ordem. Nenhuma etapa começa sem a anterior estar auditada.

## 0. Pré-requisitos (congelados antes da etapa 1)

Registrados em `protocolo/preregistro.md`:

- ID exato da rota do GPT-6 Luna Pro no OpenRouter (slug a confirmar no piloto).
- Provedor por modelo: GPT-6 Luna Pro `openai`, Claude Haiku 5.5 `anthropic`, DeepSeek V4.1 Flash `relace`.
- Teto de tempo e de orçamento por cenário.
- Limiar de sucesso autônomo e pesos dos critérios (§8.1, §8.3).
- Política de nova tentativa para `provider_error` e `harness_error`.
- Plano A ou Plano B de compatibilidade (§7.12).
- Versões de Node, Bun, browser de teste e dos três harnesses (`VERSOES.txt`).

Qualquer alteração em `docker/Dockerfile`, `VERSOES.txt` ou nos prompts depois do início da coleta é desvio de protocolo e deve ser registrada em `protocolo/checkpoints.md`.

## 1. Preparação da máquina

1. Ubuntu Server 26.04 LTS com Docker, conforme DIA 3.
2. Construir a imagem fixa:
   ```
   docker build -t tcc-harnesses:v1 -f docker/Dockerfile .
   ```
3. Confirmar as versões dentro da imagem e comparar com `VERSOES.txt`:
   ```
   docker run --rm tcc-harnesses:v1 bash -c "python3 --version; claude --version; codex --version; opencode --version"
   ```
4. Criar a rede isolada, sem saída para internet:
   ```
   docker network create --internal rede-experimento
   ```
5. Subir o 9router no host, em `tmux`, com logs de requisição:
   ```
   HOSTNAME=0.0.0.0 PORT=20128 ENABLE_REQUEST_LOGS=true 9router
   ```
6. Obter o IP do gateway da rede isolada e anotá-lo:
   ```
   docker network inspect rede-experimento -f '{{(index .IPAM.Config 0).Gateway}}'
   ```
   Se a rede for recriada, o IP muda. Repita o comando e atualize o orquestrador.
7. Desligar em `Dashboard → Endpoint → Token Saver/Ponytail` os recursos que alteram o corpo da requisição (RTK, Caveman, Ponytail, Headroom). Confirmar nos logs que o corpo repassado é igual ao recebido.

## 2. Piloto de compatibilidade (bloqueante)

O piloto não entra nos resultados finais. Usa tarefas mínimas próprias, não os starters nem os nove prompts (§7.12).

Para cada um dos nove pares harness × modelo, rodar as cinco verificações e preencher `protocolo/compatibilidade-piloto.csv`:

| # | Verificação | Como | Evidência |
|---|---|---|---|
| 1 | Consulta simples | Pergunta curta | Resposta, ID efetivo, sem erro de protocolo |
| 2 | Leitura | Pedir resumo de um `README.md` | Evento de leitura de arquivo no log |
| 3 | Edição | Pedir alteração verificável em arquivo | Arquivo modificado no disco, não só descrito |
| 4 | Execução e autocorreção | Teste simples falhando de propósito | Ciclo falha → edição → teste aprovado |
| 5 | Eventos e uso | Verificar tempo, uso, status e logs | Campos ausentes marcados `null` |

Depois do piloto:

- Pares que passam nas cinco: `compatível`.
- Pares que falham: `protocol_incompatible`, documentado. Não são convertidos em nota zero.
- Decidir Plano A (pares compatíveis, desenho incompleto declarado) ou Plano B (trocar o harness incompatível, §7.12). Registrar a decisão antes da etapa 1.
- Registrar também o consumo de tokens do piloto, que calibra a projeção da §7.8.

Comandos de referência, confirmados com `--help` da versão congelada:

```
# OpenCode (config em OPENCODE_CONFIG, fora do workspace)
opencode run --model "PROVEDOR/MODELO" --format json "$(cat prompt.txt)" > events.jsonl 2> stderr.log

# Codex (wire_api="responses"; o 9router expõe /v1/responses)
codex exec --json --model "MODELO_CONFIGURADO" - < prompt.txt > events.jsonl 2> stderr.log

# Claude Code
claude -p "$(cat prompt.txt)" --model "MODELO_CONFIGURADO" --tools "Read,Write,Edit,Bash,Glob,Grep,TodoWrite" --dangerously-skip-permissions --output-format stream-json > events.jsonl 2> stderr.log
```

Observação: as flags do Codex e do OpenCode em `config-rede.md` ainda não foram verificadas contra a versão instalada. Confirmar com `--help` antes do piloto.

## 3. Fila de execução

A fila fica em `dados/plano_162_execucoes.csv`, gerada por `scripts/gerar_fila.py` com semente `20261009`. Não editar a fila à mão. Para regenerá-la, rodar o script de novo; o resultado é idêntico.

Colunas: `ordem`, `etapa`, `condicional`, `run_id`, `cenario`, `harness`, `modelo_rotulo`, `modelo_id`, `provedor`, `prompt`, `repeticao`, `status`.

Etapas:

| Etapa | Escopo | Linhas | Condição para iniciar |
|---|---|---|---|
| 1 | R1 · site | 27 | Piloto concluído, protocolo congelado |
| — | Verificação 1 | | Etapa 1 auditada |
| 2 | R1 · jogo | 27 | Verificação 1 aprovada |
| — | Verificação 2 | | Etapa 2 auditada |
| 3 | R1 · app | 27 | Verificação 2 aprovada |
| — | Verificação 3 | | 81 execuções R1 completas e auditadas |
| 4 | R2 · site | 27 | Verificação 3 + saldo suficiente |
| 5 | R2 · jogo | 27 | Verificação 4 + saldo suficiente |
| 6 | R2 · app | 27 | Verificação 5 + saldo suficiente |

A ordem dentro de cada etapa é sorteada e registrada. Não altere a ordem à mão.

## 4. Procedimento de uma execução

Para cada linha da fila, em ordem:

1. **Selecionar a linha.** Não trocar harness, modelo, prompt ou cenário durante a rodada.
2. **Preparar o workspace.** Copiar `fixtures/<cenario>-base/` para `runs/<run_id>/workspace/`. Nunca reutilizar um workspace. Sem histórico git de outras rodadas.
3. **Preparar o HOME da rodada.** Usar um diretório descartável, sem `.claude`, `.codex` ou `CLAUDE.md`. Para o OpenCode, gravar `opencode.json` em `HOME` e apontar `OPENCODE_CONFIG` para ele.
4. **Gravar o manifesto** `runs/<run_id>/manifest.json`, antes de iniciar:
   - horário UTC de início;
   - versões de harness, roteador, runtime, browser e imagem;
   - modelo efetivo, provedor pretendido e alias;
   - hash do commit-base e do lockfile do starter;
   - hash SHA-256 do prompt;
   - limites de tempo, iterações e custo;
   - política de rede.
5. **Executar o harness em contêiner novo**, com a rede isolada e o workspace montado:
   ```
   timeout 20m docker run --rm --network rede-experimento \
     -v "$PWD/runs/<run_id>/workspace:/home/executor/trabalho" \
     -v "$PWD/prompts:/home/executor/prompts:ro" \
     tcc-harnesses:v1 bash -c "cd /home/executor/trabalho && <comando do harness>"
   ```
   Capturar `stdout` em `events.jsonl`, `stderr` em `stderr.log` e o código de saída em `summary.json`.
6. **Não intervir.** Pedidos de orientação do agente são registrados em `notes`, não respondidos. Sem testes ocultos, sem correções manuais, sem nova mensagem.
7. **Congelar a solução.** Ao fim do processo ou do limite, copiar o workspace para `runs/<run_id>/source-snapshot/` e gravar o hash. Em timeout, preservar o estado real.
8. **Rodar o avaliador independente** sobre o snapshot, fora do alcance do agente. Gerar `test-results.json` com build, unitário (Vitest), integração, E2E (Playwright) e estático (`tsc`, ESLint).
9. **Normalizar.** Converter os eventos nativos de cada harness para os campos comuns (`tool_call`, `file_change`, `command_execution`, `usage`, `run_finished`), sem apagar os brutos. Campos não observados recebem `null`, nunca zero.
10. **Gravar `summary.json`** com o esquema da §11: `run_id`, `scenario`, `harness`, `model_label`, `model_id`, `provider`, `gateway`, `prompt_level`, `repetition`, `started_at_utc`, `finished_at_utc`, `scenario_commit_sha`, `harness_version`, `prompt_sha256`, `runtime_status`, `duration_seconds`, `input_tokens`, `output_tokens`, `cached_tokens`, `cost_usd`, `cost_method`, `tool_calls`, `test_executions_by_agent`, `verified_self_corrections`, `manual_interventions`, `build_success`, `tests_passed`, `tests_total`, `reference_quality`, `prompt_adherence`, `notes`.
11. **Registrar** a linha em `dados/resultados.csv` com `status` atualizado.

## 5. Capturas obrigatórias por rodada

Cada rodada, inclusive falhas e timeouts, deixa esta estrutura:

```
runs/<run_id>/
├── manifest.json
├── prompt.txt
├── events.jsonl
├── stderr.log
├── source-snapshot/
├── test-results.json
└── summary.json
```

Além disso, guardar a captura de tráfego do 9router correspondente à rodada (`logs/`), para conferir:

- temperatura efetiva enviada, quando o harness a envia;
- provedor que atendeu, pelo `provider_name` em `https://openrouter.ai/api/v1/generation?id=GEN_ID`;
- modelo efetivo e alias resolvido.

Dado não observado é `null`. Nunca preencher com zero.

## 6. Classificação do desfecho

Duas colunas independentes, em `summary.json`:

**`runtime_status`**, um destes valores:

- `completed`: o agente encerrou sozinho.
- `timeout`: limite atingido. Tratado como censurado, nunca como sucesso.
- `provider_error`: erro de API ou provedor indisponível.
- `harness_error`: falha do ambiente ou do harness.
- `protocol_incompatible`: integração não suportada.
- `aborted`: interrompido por política, inclusive `credit_exhausted`.

**Desfecho funcional**, sobre o snapshot final: build aprovado ou não, percentual de testes aprovados e qualidade (§8.1).

Falhas de integração não são evidência de qualidade de código. Vão para série própria. Build com falha não é falha de protocolo.

Interrupção por crédito: registrar `aborted/credit_exhausted`, preservar o workspace parcial e reexecutar do zero após a recarga, ou declarar a rodada como não executada. Nunca preencher a célula com zero.

## 7. Verificações entre etapas

Ao fim de cada etapa, registrar em `protocolo/checkpoints.md`:

1. **Consumo observado:** tokens e custo da etapa, por modelo, contra o saldo restante.
2. **Projeção da próxima etapa:** usar a razão de consumo entre cenários observada no piloto, com margem de segurança de 20% (a definir). Não extrapolar diretamente da etapa anterior.
3. **Integridade:** todas as 27 execuções têm manifesto, logs, snapshot e `summary.json`. Falhas classificadas. Nenhum campo ausente preenchido com zero.
4. **Decisão:** prosseguir, ajustar ou encerrar, com data e justificativa.

Só então iniciar a etapa seguinte.

## 8. Análise de integridade antes de analisar resultados

- Cada `run_id` da fila tem uma pasta em `runs/` com as sete capturas.
- Nenhuma célula de R2 é tratada como R1 e vice-versa. A estabilidade (`S = desvio-padrão`) só existe onde há R1 e R2 executadas. Reportar `n` real por célula.
- Provedores divergentes do fixado são sinalizados. Fazer análise de sensibilidade excluindo essas rodadas e reportar se a conclusão muda.
- Interrupções por crédito e falhas de infraestrutura entram na análise de sensibilidade (§9, item 8).

## 9. Pendências antes da primeira rodada real

- Confirmar slugs do GPT-6 Luna Pro e do Claude Haiku 5.5 no OpenRouter, e os provedores efetivos (`VERSOES.txt` ainda não tem essa verificação).
- Confirmar contra `--help` as flags de Codex e OpenCode citadas em `config-rede.md`.
- Criar `fixtures/site-base`, `fixtures/jogo-base`, `fixtures/app-base` com commit, lockfile e scripts, sem solução e sem testes de avaliação.
- Criar `avaliacao/site`, `avaliacao/jogo`, `avaliacao/app` com as suítes congeladas, fora do alcance do agente.
- Criar `orchestrator/runner.py` e `orchestrator/normalizer.py`. Hoje existe só o gerador da fila.
- Decidir a política de rede do npm para os starters (§7.10 item 4).
