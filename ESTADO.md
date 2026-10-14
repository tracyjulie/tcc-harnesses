# Estado do repositório

Atualizado em 12/10/2026. Nenhuma rodada oficial foi executada: a fila está com as 162 execuções planejadas, `dados/resultados.csv` só tem o cabeçalho e não há `runs/` oficial.

## Pronto e verificado

| Item | Onde | Verificação |
|---|---|---|
| Nove prompts congelados | `prompts/*.txt` | Idênticos ao Apêndice A do plano e ao guia (comparação por script) |
| Fila de 162 execuções (semente 20261009) | `dados/plano_162_execucoes.csv` | 162 linhas, 6 etapas de 27, IDs únicos; `python3 scripts/gerar_fila.py` regenera o mesmo arquivo |
| Starters site/jogo/app | `fixtures/*-base/` | Hashes dos lockfiles conferem; `npm ci` + `npm run build` passam na imagem |
| Versões dos harnesses e da imagem | `docker/Dockerfile`, `VERSOES.txt` | Conferidas dentro da imagem em 12/10/2026 |
| Rede isolada | `rede-experimento` | `internal=true`; o contêiner não acessa a internet e alcança o roteador |
| Provedores fixados | OpenRouter, `protocolo/evidencias/` | Duas camadas de restrição (capturas); prova por chamada em `scripts/verificar_provedor.py` |
| Roteador | 9router v0.5.95 | Recursos que alteram a requisição desligados (captura) |
| Orquestrador | `orchestrator/` | `python3 -m unittest discover -s orchestrator/tests -v` (testes sem Docker e sem custo) |
| Avaliador | `avaliacao/` | Suítes validadas contra implementações de referência (10/10); repositório montado somente leitura |

## Pendente antes da Etapa 1

1. Rodar os testes do orquestrador e o `--dry-run` na imagem.
2. Colocar o painel do 9router fora do alcance do agente (proxy que só expõe `/v1/`, ver `MANUAL-RODADAS.md` seção 1).
3. Gerar o congelamento: `python3 orchestrator/preflight.py --gerar-congelamento`.
4. Refazer o piloto de compatibilidade dos 9 pares com as verificações novas (gasta crédito; exige OK da pesquisadora).
5. Rodar os controles negativos do avaliador (starter vazio não pode pontuar) e decidir a política para critérios não observados no jogo e no app (`avaliacao/METODOLOGIA.md`).
6. Revisar com o orientador: pesos, mapeamento critério × prompt, contrato do app, política de nulos.
7. Registrar o saldo experimental oficial (previsto: US$ 20,00) e criar a tag `congelamento-v1`.

## Como reproduzir o que existe

```
cd tcc-harnesses
python3 scripts/gerar_fila.py                      # regenera a fila
python3 -m unittest discover -s orchestrator/tests -v
python3 orchestrator/runner.py --limit 2 --dry-run --no-gateway
python3 orchestrator/preflight.py --verificar-ambiente
```
