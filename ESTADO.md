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
| Slugs e provedores no OpenRouter | `VERSOES.txt`, `protocolo/preregistro.md` | Modelo alvo e `GPT-6 Luna` (`openai/gpt-6-luna`); o 9router atual so lista `openai/gpt-6-luna-pro` (bloqueado por guardrail), a corrigir antes do piloto |
| Starters site, jogo e app | `fixtures/*-base/` | `npm run build` passou nos tres (exit 0) |
| Lockfile hashes e versao do Node | `fixtures/README.md` | Node 22.17.0; hashes calculados em 10/10/2026 |
| Protocolo: pre-registro, checkpoints, piloto, resultados vazios | `protocolo/`, `dados/resultados.csv` | Templates, nao preenchidos |
| Manual de rodadas | `MANUAL-RODADAS.md` | Procedimento escrito; nao executado |

## O que esta parcial ou nao verificado

- **`avaliacao/`**: suites Playwright (`site/tests`, `jogo/tests`, `app/tests`), `shared/helpers.mjs`, configs por cenario e o avaliador `avaliar.py` (build em copia, servidor em porta livre com `--strictPort`, testes, agregacao). **Validado de ponta a ponta no servidor** contra `site-base` (starter vazio): build aprovado, Playwright conecta, `test-results.json` gerado com motivos corretos. Playwright fixado em 1.64.0 (1.55.0 nao suporta Ubuntu 26.04). **Ressalva:** o avaliador roda com o Node do host (20); o cenario `app` exige Node 22 (`node:sqlite`), entao o avaliador deve rodar dentro da imagem (Node 22) antes da coleta. Testes de jogo (pixels) e criterios de API do app (A02-A10) seguem heuristicos ou `null` ate congelamento dos contratos.
- **`avaliacao/mapeamento-criterio-prompt.json`**: marcado como `rascunho - aprovar antes da coleta`. Precisa de aprovacao do pesquisador.
- **`orchestrator/`**: criados `runner.py` (fila + piloto, seguindo `MANUAL-RODADAS.md` secao 4), `normalizer.py` (conceitos comuns, sem inventar valores), `adapters/` (comando por harness) e `modelos.json` (vazio; preencher no piloto). Sintaxe validada com `py_compile`; **nao** executado contra os harnesses reais.
- **Flags dos harnesses** (`config-rede.md`): **confirmadas** com `--help` na imagem `tcc-harnesses:v1` (Claude 2.1.197, Codex 0.160.0, OpenCode 1.18.34). Comandos efetivos ajustados em `orchestrator/adapters/` (Codex `--skip-git-repo-check` e bypass de sandbox; OpenCode `--auto`; Claude `--verbose`).
- **Ligacao ao 9router**: o runner descobre o gateway da rede (`172.18.0.1:20128`), le a chave de `~/.tcc-segredos/9router.key`, gera `opencode.json`/`.codex/config.toml` e exporta `OPENAI_*`/`ANTHROPIC_*`. Piloto `--pilot --pilot-model deepseek` passou nos **3 harnesses** (`compativel` em autentica/le/edita/executa/gera_logs). `modelos.json` preenchido com as rotas `openrouter/...`.
- **Node da imagem**: o `Dockerfile` instalava Node 20, mas os starters exigem Node 22 (`node:sqlite` do app). **Corrigido para Node 22 e imagem reconstruida** em 10/10/2026 (`tcc-harnesses:v1`, Node v22.23.3, npm 10.9.9).
- **Provedor efetivo por rodada**: nao verificado. So sera confirmado no piloto, pelo `provider_name` do OpenRouter.
- **Politica de rede do npm** para os starters: nao decidida (§7.10 item 4).
- **SQLite no app-base**: usa `node:sqlite`, decisao a aprovar.
- **`VERSOES.txt`**: Docker do Ubuntu e Node da imagem preenchidos (29.8.2; Node 22.23.3).

## Proximos passos, em ordem

1. Adicionar/disponibilizar `openai/gpt-6-luna` no 9router/OpenRouter (hoje so existe `gpt-6-luna-pro`, bloqueado por guardrail) e confirmar o slug.
2. Rodar o piloto completo dos 9 pares: `python orchestrator/runner.py --pilot`. Registrar em `protocolo/compatibilidade-piloto.csv`.
3. Aprovar `mapeamento-criterio-prompt.json`, a politica de rede do npm e a decisao de SQLite; congelar o contrato de API do app (`avaliacao/app/contrato.json`).
4. Rodar o avaliador dentro da imagem (Node 22) para o cenario `app`.
5. Decidir Plano A ou B e preencher `protocolo/preregistro.md`.
6. Iniciar a etapa 1 (site, R1): `python orchestrator/runner.py --etapa 1`.

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
