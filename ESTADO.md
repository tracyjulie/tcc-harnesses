# Estado do repositorio

Ultima atualizacao: 10/10/2026. Commit em `origin/main`: `5682989`.

> Um commit anterior (`f0f1cf4`), produzido por outro agente, foi desfeito do `origin/main` por conter dados de verificacao fabricados (flags e slugs "confirmados" sem execucao, versao de Docker inventada, `normalizer.py` com resultados fixos). Ele permanece apenas como tag local `agente-ruim-f0f1cf4` para auditoria.

## O que esta feito e verificado

| Item | Onde | Verificacao |
|---|---|---|
| Nove prompts congelados (Apendice A do plano v2) | `prompts/*.txt` | Extraidos automaticamente do plano |
| Fila de 162 execucoes, semente 20261009 | `dados/plano_162_execucoes.csv`, `scripts/gerar_fila.py` | 162 linhas, 6 etapas de 27, IDs unicos |
| Versoes dos harnesses fixadas | `docker/Dockerfile` | Existem no npm: claude-code 2.1.197, codex 0.160.0, opencode-ai 1.18.34 |
| Registro de versoes | `VERSOES.txt` | Docker 28.5.2 no host Windows; versao do Ubuntu ainda em branco |
| Slugs e provedores no OpenRouter | `VERSOES.txt`, `protocolo/preregistro.md` | Modelos existem: `openai/gpt-6-luna-pro`, `anthropic/claude-haiku-5.5`, `deepseek/deepseek-v4.1-flash`. Provedores `openai`, `anthropic` e `relace` aparecem na lista |
| Starters site, jogo e app | `fixtures/*-base/` | `npm run build` passou nos tres (exit 0) |
| Lockfile hashes e versao do Node | `fixtures/README.md` | Node 22.17.0; hashes calculados em 10/10/2026 |
| Protocolo: pre-registro, checkpoints, piloto, resultados vazios | `protocolo/`, `dados/resultados.csv` | Templates, nao preenchidos |
| Manual de rodadas | `MANUAL-RODADAS.md` | Procedimento escrito; nao executado |

## O que esta parcial ou nao verificado

- **`avaliacao/`**: alem dos pesos, `score.py` e `shared/collect.mjs`, agora existem as suites Playwright (`site/tests`, `jogo/tests`, `app/tests`), `shared/helpers.mjs`, configs por cenario e o avaliador `avaliar.py` (build, servidor, testes, agregacao). O fluxo de partes -> `collect.mjs` -> `score.py` foi validado com resultados simulados. **Ainda nao executado** contra um snapshot real de agente (exige `npm install` do Playwright e o build do starter). Os testes de jogo (pixels) e os criterios de API do app (A02-A10) permanecem heuristicos ou `null` ate o congelamento dos contratos.
- **`avaliacao/mapeamento-criterio-prompt.json`**: marcado como `rascunho - aprovar antes da coleta`. Precisa de aprovacao do pesquisador.
- **`orchestrator/`**: criados `runner.py` (fila + piloto, seguindo `MANUAL-RODADAS.md` secao 4), `normalizer.py` (conceitos comuns, sem inventar valores), `adapters/` (comando por harness) e `modelos.json` (vazio; preencher no piloto). Sintaxe validada com `py_compile`; **nao** executado contra os harnesses reais.
- **Flags dos harnesses** (`config-rede.md`): nao confirmadas com `--help` nas versoes fixadas. A verificacao falhou por erro de credito.
- **Provedor efetivo por rodada**: nao verificado. So sera confirmado no piloto, pelo `provider_name` do OpenRouter.
- **Politica de rede do npm** para os starters: nao decidida (§7.10 item 4).
- **SQLite no app-base**: usa `node:sqlite`, decisao a aprovar.
- **`VERSOES.txt`**: campo do Docker no Ubuntu ainda em branco.

## Proximos passos, em ordem

1. Rodar `--help` das versoes fixadas e confirmar as flags de Claude Code, Codex e OpenCode; corrigir `config-rede.md`.
2. Preencher `orchestrator/modelos.json` com o identificador exato de cada harness (confirmado no piloto).
3. Instalar o Playwright (`npx playwright install chromium`) e rodar as suites contra um snapshot de teste; congelar a versao dos testes.
4. Aprovar `mapeamento-criterio-prompt.json`, a politica de rede do npm e a decisao de SQLite; congelar o contrato de API do app (`avaliacao/app/contrato.json`).
5. Construir a imagem `tcc-harnesses:v1` no Ubuntu, anotar o Docker no `VERSOES.txt`.
6. Rodar o piloto: `python orchestrator/runner.py --pilot`. Registrar em `protocolo/compatibilidade-piloto.csv`.
7. Decidir Plano A ou B e preencher `protocolo/preregistro.md`.
8. Iniciar a etapa 1 (site, R1): `python orchestrator/runner.py --etapa 1`.

**Pendencia de ambiente:** os starters sao copiados sem `node_modules` (ignorado no git). Decidir se as dependencias ficam pre-instaladas na imagem ou se o runner deve rodar `npm ci` antes da rodada (a politica de rede do npm ainda nao foi definida).

## Como reproduzir o que existe

```
cd tcc-harnesses
python scripts/gerar_fila.py              # regenera dados/plano_162_execucoes.csv
for c in site jogo app; do (cd fixtures/$c-base && npm ci && npm run build); done
sha256sum fixtures/*-base/package-lock.json
```

## Creditos

Os erros 402 da sessao vieram do gateway local (`127.0.0.1:20128`, o 9router) ao OpenRouter. Os subagentes usam a mesma cota. Para economizar credito:
- Nao abrir novos subagentes para tarefas que podem ser feitas direto.
- Concluir o orquestrador e os testes localmente antes de gastar credito no piloto, que e o primeiro consumo real.
- Recarregar o OpenRouter antes do piloto. O custo do piloto calibra a projecao da etapa 1 (§7.8).
