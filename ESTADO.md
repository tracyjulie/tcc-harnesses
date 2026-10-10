# Estado do repositorio

Ultima atualizacao: 10/10/2026. O commit deste arquivo e o estado canonico
(nao citamos mais um hash fixo aqui, para nao ficar desatualizado; ver
`git log --oneline -1`).

> **HANDOFF.** Para continuar em um contexto novo, leia
> `TCC/documentacao/PROXIMOS-PASSOS.md` (fora deste repositorio). Ele tem o
> estado completo, as pendencias e a ordem de trabalho. Este arquivo e o resumo.

## Avisos de processo (importante)

- A **Etapa 1 (coleta real) foi iniciada por engano** por um agente anterior,
  sem aprovacao e sem o `preregistro.md` congelado. Foi **PARADA e RESETADA**:
  a fila voltou a **162 planejadas** e `runs/` e `dados/resultados.csv` foram
  limpos. **Nada esta rodando.**
- A fila no servidor tinha apenas uma alteracao de fim-de-linha nao commitada;
  foi descartada e o servidor sincronizado (10/10/2026).
- Um commit anterior (`f0f1cf4`) foi desfeito por conter verificacoes
  fabricadas; permanece so como tag local `agente-ruim-f0f1cf4`.

## O que esta feito e verificado

| Item | Onde | Verificacao |
|---|---|---|
| Nove prompts congelados | `prompts/*.txt` | Extraidos do Apendice A; aplicados verbatim |
| Fila de 162 execucoes (semente 20261009) | `dados/plano_162_execucoes.csv` | 162 linhas, 6 etapas de 27, IDs unicos |
| Starters site/jogo/app | `fixtures/*-base/` | `npm ci` + `npm run build` passam na imagem (Node 22) |
| Versoes dos harnesses | `docker/Dockerfile`, `VERSOES.txt` | Claude 2.1.197, Codex 0.160.0, OpenCode 1.18.34 |
| Imagem com Node 22 | `docker/Dockerfile` | `tcc-harnesses:v1` (id 6da2ef8ed08d), Node v22.23.3 |
| Ligacao ao 9router | `orchestrator/runner.py`, `modelos.json` | gateway `172.18.0.1:20128`, chave em `~/.tcc-segredos/9router.key` |
| Piloto de compatibilidade | `protocolo/compatibilidade-piloto.csv` | 9/9 pares compativeis (10/10/2026) |
| Decisoes congeladas | `protocolo/preregistro.md` | Preenchido e datado em 10/10/2026 |
| Custo/tokens efetivos | `orchestrator/router_logs.py` | le `~/.9router/db/data.sqlite` (usageHistory) |
| Avaliador em Node 22 | `runner.py` (`--evaluator container`) | roda na imagem, browsers do host montados |
| Metodologia do instrumento | `avaliacao/METODOLOGIA.md` | proxies do jogo e descoberta do app documentados |

## Resolvido nesta sessao (10/10/2026)

1. **P1** - Criterios ativados em `avaliacao/*/pesos.json` (todos `verificavel:true`)
   e suites reescritas para site (S01-S10), jogo (J01-J10) e app (A01-A10).
2. **P2** - Temperatura 0 fixada no OpenCode (`agent.build.temperature`);
   `reasoning_tokens` efetivo registrado por rodada a partir do 9router;
   limitacoes de Claude/Codex documentadas.
3. **P3** - Custo e tokens lidos do `usageHistory` do 9router
   (`router_logs.py`); `cost_method` corrigido; ausencia vira `null`.
4. **P4** - Avaliador roda em contêiner Node 22; app tem `start_cmd`
   descoberto e portas testadas.
5. **P5** - `preregistro.md` com todas as decisoes (tempo 20 min, custo US$ 2,
   sucesso = build + B >= 50, retry 1, npm so no preparo).
6. **P6** - Contrato do app decidido: descoberta de rotas pela interface/rede;
   fallback `NAO_OBSERVADO` (null); alternativa a ratificar em `contrato.json`.
7. **P7** - Node fixado em 22.23.3; Bun nao usado; browsers Playwright 1.64.0;
   Python do orquestrador no host (3.14.4, compativel com 3.10.10). Ver `VERSOES.txt`.
8. **P8** - `checkpoints.md` mantido como template (a preencher a cada etapa),
   com referencia as decisoes congeladas.
9. **Doc** - `ESTADO.md`, `MANUAL-RODADAS.md`, `README.md`, `VERSOES.txt`,
   starters e `modelos.json` atualizados.

## Validacao do instrumento (10/10/2026)

As suites foram executadas contra **implementacoes de referencia** em
`avaliacao/_referencia/` (fora dos starters, fora do alcance do agente), no
conteiner Node 22. Resultado: **site 10/10, jogo 10/10, app 10/10**.

Falhas reais encontradas e corrigidas durante a validacao:
- starters sem `src/vite-env.d.ts` (importar CSS quebrava o `tsc`) -> adicionado;
- `collect.mjs` ignorava as partes de build (boolean `true/false` vs `1/0`) -> normalizado;
- imagem sem as libs do Chromium -> adicionadas e imagem reconstruida;
- deps do avaliador desatualizadas -> pinadas por `avaliacao/*/package-lock.json`.

Convencoes do instrumento (a ratificar):
- **jogo:** descoberta de um objeto de estado em `window` (ex.: `window.__labirinto`);
  sem ele, J03/J04/J05/J06/J09 ficam `null` (`NAO_OBSERVADO`);
- **app:** descoberta de rotas/autenticacao pela interface e rede, sem fixar rotas.

## O que permanece pendente

1. **P9** - Refazer o piloto de compatibilidade com o runner/avaliador atualizados
   (gasta credito; requer OK da pesquisadora).
2. **Publicar no GitHub** - a ultima sessao nao conseguiu `git push` (credencial
   expirada). Os commits estao no repo local do Windows e no servidor (via bundle),
   mas ainda **nao estao em `origin/main`**. Rodar `git push` apos reautenticar.
3. **Ratificar** o contrato do app e a convencao de estado do jogo
   (`avaliacao/METODOLOGIA.md`).
4. **Iniciar a Etapa 1** - somente apos P9 aprovado e protocolo congelado.

## Como reproduzir o que existe

```
cd tcc-harnesses
python scripts/gerar_fila.py                 # regenera a fila
python3 orchestrator/runner.py --limit 2 --dry-run
python3 orchestrator/runner.py --limit 2 --dry-run --evaluator host
for c in site jogo app; do (cd fixtures/$c-base && npm ci && npm run build); done
python3 avaliacao/avaliar.py /tmp/val-site site /tmp/val-run         # host
# ou, no servidor, dentro do contêiner Node 22 (recomendado):
docker run --rm -v "$PWD:/repo" -v "$HOME/.cache/ms-playwright:/evalcache:ro" \
  -e PLAYWRIGHT_BROWSERS_PATH=/evalcache -w /repo tcc-harnesses:v1 \
  python3 /repo/avaliacao/avaliar.py /repo/runs/<id>/source-snapshot site /repo/runs/<id>
```
