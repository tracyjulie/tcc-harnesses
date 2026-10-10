# Implementações de referência

Soluções canônicas dos três cenários, **fora dos starters** e **fora do alcance
do agente**, usadas apenas para **validar o instrumento** (as suítes de
`avaliacao/`). Não fazem parte do experimento e não são entregues ao agente.

- `site/` — TecnoIF 2026 (Vite + TS).
- `jogo/` — Labirinto Explorer (Vite + TS + Canvas).
- `app/` — ReservaFácil (React + TS + Hono + node:sqlite).

Como validar (no servidor, dentro do contêiner Node 22):

```
docker run --rm -v "$HOME/tcc-harnesses:/repo" \
  -v "$HOME/.cache/ms-playwright:/evalcache:ro" \
  -e PLAYWRIGHT_BROWSERS_PATH=/evalcache -w /repo tcc-harnesses:v1 \
  python3 /repo/avaliacao/avaliar.py /repo/avaliacao/_referencia/<cenario> <cenario> /tmp/val-<cenario>
```

Depois conferir `test-results.json`, `avaliacao.log` e `avaliacao-resultados/`.
