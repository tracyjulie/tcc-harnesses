# Estado do repositorio

Ultima atualizacao: 10/10/2026. Commit em `origin/main`: `5253a20`.

> **HANDOFF.** Para continuar em um contexto novo, leia
> `TCC/documentacao/PROXIMOS-PASSOS.md` (fora deste repositorio). Ele tem o estado
> completo, as pendencias e a ordem de trabalho. Este arquivo e o resumo.

## Avisos de processo (importante)

- A **Etapa 1 (coleta real) foi iniciada por engano**, sem aprovacao do pesquisador
  e sem o `preregistro.md` congelado. Foi **PARADA e RESETADA**: a fila voltou a
  **162 planejadas** e `runs/` e `dados/resultados.csv` foram limpos. **Nada esta
  rodando.**
- O **piloto (9/9 compativel)** foi aprovado sem que as pendencias estivessem
  resolvidas. Nao tratar como "aprovacao" ate refazer com o avaliador completo.
- Um commit anterior (`f0f1cf4`, de outro agente) foi **desfeito** do `origin/main`
  por conter verificacoes fabricadas. Permanece so como tag local
  `agente-ruim-f0f1cf4`, para auditoria.

## O que esta feito e verificado

| Item | Onde | Verificacao |
|---|---|---|
| Nove prompts congelados | `prompts/*.txt` | Extraidos do Apendice A do plano |
| Fila de 162 execucoes (semente 20261009) | `dados/plano_162_execucoes.csv` | 162 linhas, 6 etapas de 27, IDs unicos |
| Starters site/jogo/app | `fixtures/*-base/` | `npm ci` + `npm run build` passam na imagem (Node 22) |
| Versoes dos harnesses | `docker/Dockerfile`, `VERSOES.txt` | Claude 2.1.197, Codex 0.160.0, OpenCode 1.18.34 |
| Imagem com Node 22 | `docker/Dockerfile` | `tcc-harnesses:v1`, Node v22.23.3, npm 10.9.9 |
| Flags confirmadas | `config-rede.md`, `orchestrator/adapters/` | `--help` na imagem; Codex `--skip-git-repo-check`+bypass, OpenCode `--auto`, Claude `--verbose` |
| Ligacao ao 9router | `orchestrator/runner.py`, `modelos.json` | gateway `172.18.0.1:20128`, chave em `~/.tcc-segredos/9router.key` |
| Captura de tokens | `orchestrator/normalizer.py` | input/output/cache por harness (validado em rodada real) |
| Preparo de dependencias | `runner.py` (`preparar_dependencias`) | `npm ci` em passo com rede, antes do isolamento |
| Piloto de compatibilidade | `protocolo/compatibilidade-piloto.csv` | **9/9 pares compativeis** (10/10/2026) |
| Suites de avaliacao | `avaliacao/`, `avaliar.py` | fluxo validado de ponta a ponta (build->servidor->Playwright->collect->score) |

## O que esta errado ou pendente (ver handoff para detalhes)

1. **Criterios desativados**: `avaliacao/*/pesos.json` marca muitos criterios como
   `verificavel:false`; sem teste eles ficam `null` e **seu peso nao entra na nota**.
   Contraria o §8.1 do plano. E preciso ativar todos e reescrever as suites.
2. **Parametros de inferencia** (temperatura / esforco de raciocinio) nao equalizados
   (§7.10 item 7).
3. **Custo do OpenCode = 0,0** (deve vir dos logs do 9router).
4. **Avaliador do `app`** roda com o Node 20 do host; o app exige Node 22.
5. **`preregistro.md`** com fatos preenchidos, mas as decisoes ainda em aberto
   (tetos, limiar, retry, pesos, mapeamento, contrato do app, npm).
6. **Node 22.17.0 (README) vs 22.23.3 (imagem)** e Python do host (3.14) vs alvo (3.10).
7. **`avaliacao/mapeamento-criterio-prompt.json`** e o contrato do app continuam rascunho.

## Como reproduzir o que existe

```
cd tcc-harnesses
python scripts/gerar_fila.py                 # regenera a fila
python3 orchestrator/runner.py --limit 2 --dry-run
for c in site jogo app; do (cd fixtures/$c-base && npm ci && npm run build); done
python3 avaliacao/avaliar.py /tmp/val-site site /tmp/val-run   # avaliador
```
