# tcc-harnesses

Impacto do Harness de Agentes de Programação na Qualidade do Software Gerado.
Estudo experimental comparativo entre Claude Code, Codex e OpenCode sob três
modelos, três cenários (site, jogo, app) e três níveis de prompt.

## Comece por aqui

- `ESTADO.md` — resumo do estado e do que está pendente.
- `MANUAL-RODADAS.md` — procedimento de piloto e coleta.
- `protocolo/preregistro.md` — decisões congeladas antes da coleta.
- `VERSOES.txt` — versões e decisões de ambiente.
- `avaliacao/METODOLOGIA.md` — como o avaliador mede cada critério.

## Estrutura

```
protocolo/     preregistro, checkpoints, piloto de compatibilidade
prompts/       os nove enunciados congelados (site/jogo/app × P1-P3)
fixtures/      starters dos três cenários (sem solução e sem testes)
avaliacao/     avaliador independente (Playwright) + regras de pontuação
orchestrator/  runner, normalizer, adapters, leitura do 9router
docker/        imagem fixa do experimento (Node 22)
dados/         fila de 162 execuções e resultados
```

Comandos úteis:

```
python scripts/gerar_fila.py
python3 orchestrator/runner.py --limit 2 --dry-run
python3 orchestrator/runner.py --pilot            # piloto de compatibilidade
python3 orchestrator/runner.py --etapa 1          # coleta (só com protocolo congelado)
```

A coleta real não deve ser iniciada sem aprovação explícita da pesquisadora e
sem o `preregistro.md` congelado.
