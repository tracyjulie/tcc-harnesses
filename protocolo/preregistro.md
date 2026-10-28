# Pré-registro

Decisões congeladas antes da coleta definitiva, conforme a §7.8 do plano de trabalho. O que o plano ainda não define consta como **A DEFINIR** e deve ser preenchido antes do congelamento.

## Identificação

| Campo | Valor |
|---|---|
| Trabalho | Impacto do Harness de Agentes de Programação na Qualidade, Eficiência e Autonomia do Código Gerado |
| Plano de referência | `plano-tcc-harnesses-v3.md` |
| Orientador | Prof. Ricardo Maroquio |
| Situação | Rascunho |
| Data do congelamento | A DEFINIR |

## 1. Desenho experimental

| Item | Valor |
|---|---|
| Harnesses | OpenCode · Codex · Claude Code |
| Modelos | GPT-6 Luna · Claude Haiku 5.5 · DeepSeek V4.1 Flash |
| Cenários | TecnoIF 2026 (baixa) · Labirinto Explorer (média) · ReservaFácil (alta) |
| Prompts | P1 (resumido) · P2 (intermediário) · P3 (detalhado), cruzados com todos os cenários |
| Repetições | R1 · R2 (R2 condicionada ao saldo) |
| Condições | 81 |
| Execuções planejadas | 81 (R1) + 81 (R2) = 162 |
| Desenho mínimo | R1 completa (81 execuções) |
| Identificador da execução | `CENARIO-HARNESS-MODELO-PROMPT-REPETICAO` |
| Prompts | Nove enunciados congelados, aplicados *verbatim*, um por execução |
| Projeto-base | Starter versionado por cenário, mesmo commit em todas as rodadas do cenário, sem solução e sem testes de avaliação |
| Contingência | A redução recai primeiro sobre as etapas de maior custo; nenhuma célula não executada é preenchida ou tratada como nota zero; persistindo a restrição, corta-se um modelo inteiro |
| Modelo a cortar, se necessário | A DEFINIR |
| Plano de compatibilidade (A ou B) | A DEFINIR, após o piloto |

## 2. Modelos e rotas

| Modelo | Rótulo no ID | ID de rota | Provedor fixado |
|---|---|---|---|
| GPT-6 Luna | `LUNA` | `gpt-6-luna` (OpenRouter: `openai/gpt-6-luna`) | OpenAI |
| Claude Haiku 5.5 | `HAIKU` | `claude-haiku-5-5` | Anthropic |
| DeepSeek V4.1 Flash | `DEEPSEEK` | `deepseek-v4.1-flash` | Relace |

| Item | Valor |
|---|---|
| Variante Pro do GPT-6 | Não utilizada |
| Fixação do provedor | No OpenRouter, por modelo |
| Provedor efetivo | Capturado nos metadados de cada resposta; divergências sinalizadas |
| Indisponibilidade da Relace | Registrada como `provider_error`, sem troca silenciosa de provedor |

## 3. Fila de execução

| Etapa | Escopo | Execuções | Condição para iniciar |
|---:|---|---:|---|
| 1 | R1 · TecnoIF 2026 | 27 | Piloto concluído e protocolo congelado |
| 2 | R1 · Labirinto Explorer | 27 | Verificação 1 aprovada |
| 3 | R1 · ReservaFácil | 27 | Verificação 2 aprovada |
| 4 | R2 · TecnoIF 2026 | 27 | Verificação 3 e saldo suficiente |
| 5 | R2 · Labirinto Explorer | 27 | Verificação da etapa 4 e saldo suficiente |
| 6 | R2 · ReservaFácil | 27 | Verificação da etapa 5 e saldo suficiente |

| Item | Valor |
|---|---|
| Ordem dentro de cada etapa | Sorteada com semente `20261009` |
| Fila completa | `dados/plano_162_execucoes.csv`, com os campos `etapa` e condicionalidade das etapas 4 a 6 |
| Verificação entre etapas | Consumo observado, projeção da etapa seguinte, integridade e decisão, registrados em `protocolo/checkpoints.md` |
| Margem de segurança da projeção | A DEFINIR (sugestão do plano: 20%) |
| Interrupção por falta de crédito | `aborted` com motivo `credit_exhausted`; reexecução do zero após a recarga ou declarada não executada |

## 4. Limites e orçamento

| Cenário | Teto de tempo | Teto de custo |
|---|---|---|
| TecnoIF 2026 | A DEFINIR | A DEFINIR |
| Labirinto Explorer | A DEFINIR | A DEFINIR |
| ReservaFácil | A DEFINIR | A DEFINIR |

| Item | Valor |
|---|---|
| Aplicação dos tetos | Iguais para todas as combinações do cenário; definidos após o piloto |
| Saldo de créditos inicial | A DEFINIR |
| Nova tentativa para `provider_error` e `harness_error` | A DEFINIR (se haverá reexecução e quantas, preservando o registro da tentativa original) |

## 5. Ambiente e isolamento

| Item | Valor |
|---|---|
| Execução | Contêiner Docker em servidor Ubuntu dedicado |
| Workspace | Cópia do commit-base do starter em `runs/<id-da-execucao>/`, novo a cada rodada |
| Dependências | `npm ci` com *lockfile*, pré-instaladas no starter |
| Configuração global | Escopos globais esvaziados, `HOME` descartável; *skills*, MCPs extras, regras globais e agentes auxiliares desabilitados; padrões do harness mantidos e registrados |
| Rede | Busca e obtenção de conteúdo web desabilitadas; única saída é o endpoint do roteador |
| Instalação adicional de pacotes | A DEFINIR (somente se o piloto mostrar necessidade) |
| Permissões | Regime autônomo equivalente nos três harnesses |
| Testes de avaliação | Em `avaliacao/`, fora do alcance do agente |
| Intervenção durante a rodada | Nenhuma; pedidos de orientação do agente são registrados, não respondidos |
| Conformidade | Verificada automaticamente antes de cada rodada |
| Roteador | 9router |
| Parâmetros de inferência | Temperatura e esforço de raciocínio equalizados por equivalência operacional; valores A DEFINIR; valor efetivo sempre registrado |

| Versão congelada | Valor |
|---|---|
| Node.js / Bun | A DEFINIR |
| Browser de teste | A DEFINIR |
| Claude Code | A DEFINIR |
| Codex | A DEFINIR |
| OpenCode | A DEFINIR |
| Roteador (9router) | A DEFINIR |
| Imagem do contêiner | A DEFINIR |
| Commit e *lockfile* dos starters | A DEFINIR |

## 6. Piloto de compatibilidade

| Item | Valor |
|---|---|
| Caráter | Obrigatório e bloqueante; resultados fora dos resultados finais |
| Pares testados | 9 (3 harnesses × 3 modelos) |
| Verificações por par | Consulta simples · leitura de repositório · edição de arquivo · execução e autocorreção · coleta de eventos e uso |
| Tarefas | Mínimas e próprias; não usa os nove prompts nem os starters |
| Consumo | Registrado, para calibrar a projeção das verificações |

## 7. Desfecho de cada rodada

| Item | Valor |
|---|---|
| Estado de execução (`runtime_status`) | `completed` · `timeout` · `provider_error` · `harness_error` · `protocol_incompatible` · `aborted` |
| `timeout` | Desfecho censurado, nunca sucesso |
| Desfecho funcional | Calculado sobre o snapshot final, definido apenas para rodadas com artefato |
| Falhas de integração (`protocol_incompatible`, `harness_error`, `provider_error`) | Não são evidência de qualidade de código; contabilizadas em série própria |

## 8. Métricas e instrumentos

| Item | Valor |
|---|---|
| Casos de teste | Binários (aprovado = 1, reprovado = 0), sem pesos, sem crédito parcial e sem limiar de aprovação; lista no Anexo A |
| Mapeamento critério × prompt | A DEFINIR (define o denominador do indicador A) |
| Qualidade de referência (B) | `Q = 100 × Σ aprovadoᵢ / N`, com N = total de casos do cenário |
| Aderência ao prompt (A) | `Q = 100 × Σ aprovadoᵢ / N`, com N = casos explicitamente solicitados no prompt (P1, P2 ou P3) |
| Qualidade por custo | `Ec = Q / Custo_USD`; não calculada se o custo for zero, ausente ou desconhecido |
| Qualidade por tempo | `Et = Q / Tempo_min`; timeout entra como desfecho censurado |
| Sucesso autônomo | `runtime_status = completed`, build aprovado e conclusão sem intervenção humana; sem limiar de qualidade |
| Taxa de autonomia | `A_aut = 100 × Sucessos sem ajuda / Execuções elegíveis` |
| Estabilidade | `S = desvio-padrão(Q em R1, R2)`, com a amplitude `|R1 − R2|`, apenas onde existem R1 e R2 |
| Dado não observado | `null`, nunca zero |
| Custo | `cost_method` registrado por rodada; custo ausente é "não mensurável", não zero |
| Composição | Métricas mantidas separadas, sem índice composto |

| Nível de teste | Instrumento |
|---|---|
| Build | Comando de build no snapshot final |
| Unitário | Vitest |
| Integração | Vitest e requisições HTTP ao servidor |
| E2E | Playwright |
| Estático | TypeScript (`tsc`) e ESLint |

| Prioridade | Métricas |
|---|---|
| Primárias | Qualidade de referência (B) · aderência ao prompt (A) · sucesso de build · conclusão sem intervenção · tempo decorrido · custo de inferência · testes aprovados |
| Secundárias | Chamadas de ferramenta · execuções de testes pelo agente · autocorreções verificadas · tokens de entrada, saída e cache · erros de tipagem e violações de *lint* (exploratória) |
| Controle | Erros e timeouts |

## 9. Análise

| Item | Valor |
|---|---|
| Comparação do efeito do harness | Em blocos equivalentes, com modelo, cenário e prompt fixos |
| Interações | Harness × modelo; harness × nível de prompt |
| Métodos | Comparações pareadas, não paramétricos ou de reamostragem; sem modelos excessivamente parametrizados |
| Células com `n` distinto | Não são agregadas como equivalentes; `n` real sempre reportado |
| Análises de sensibilidade | (i) sem rodadas com falha de infraestrutura, desvio de provedor ou interrupção por limite; (ii) por tipo de rota (esperada × sem suporte oficial); (iii) etapas completas × parcialmente cobertas por R2 |

## 10. Decisões com justificativa

| Decisão | Valor | Justificativa |
|---|---|---|
| Stack nos starters | Incluída nos três starters, ausente dos prompts | Torna P1 (stack livre) e P2/P3 (stack exigida) comparáveis |
| Provedor do DeepSeek | Relace | O provedor oficial está inativo na plataforma |
| Fixação de provedor por modelo | Configuração do OpenRouter | Evita variação de quantização, latência e comportamento entre provedores |
| Ordem sorteada dentro das etapas | Semente `20261009` | Evita associar horário, carga e disponibilidade do provedor a um harness ou modelo |
| Piloto com tarefas próprias | Não usa os prompts nem os starters | Poupa créditos |
| Casos de teste sem pesos | Todos valem o mesmo | Qualidade é o próprio percentual de casos aprovados |

## Anexo A. Casos de teste

### TecnoIF 2026 (site)

| ID | Comportamento verificado |
|---|---|
| S01 | Projeto compila e aplicação abre |
| S02 | Seções navegáveis e semântica adequada |
| S03 | Lista das seis palestras e trilhas corretas |
| S04 | Filtro de trilhas funciona corretamente |
| S05 | Três palestrantes apresentados |
| S06 | Formulário aceita inscrição válida |
| S07 | Formulário rejeita entradas inválidas |
| S08 | Inscrições persistem após recarga |
| S09 | Inscrições repetidas são bloqueadas |
| S10 | Layout utilizável em 360/768/1440 px |

### Labirinto Explorer (jogo)

| ID | Comportamento verificado |
|---|---|
| J01 | Projeto compila, abre e desenha o tabuleiro |
| J02 | Movimento pelas quatro direções |
| J03 | Paredes impedem deslocamento |
| J04 | Chaves são coletadas e contabilizadas |
| J05 | Saída só permite vitória após três chaves |
| J06 | Colisões com inimigos reduzem vidas |
| J07 | Pontuação e cronômetro evoluem corretamente |
| J08 | Pausa congela tempo e movimentação |
| J09 | Reinício restaura estado inicial |
| J10 | Recorde persiste entre partidas |

### ReservaFácil (aplicação)

| ID | Comportamento verificado |
|---|---|
| A01 | Servidor e frontend iniciam sem erro |
| A02 | Login, logout e proteção de endpoints |
| A03 | Usuário comum não modifica reservas alheias |
| A04 | Administrador gerencia salas |
| A05 | CRUD de reservas é persistente |
| A06 | Filtros por sala, data e usuário |
| A07 | Sobreposição de horários é rejeitada |
| A08 | Dados inválidos são rejeitados no backend |
| A09 | Concorrência não permite conflito duplo |
| A10 | Histórico registra criação, edição e cancelamento |
