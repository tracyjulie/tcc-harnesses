# Starters (fixtures)

Projetos-base dos três cenários (plano v2, §7.4 e §7.10). Cada um contém apenas a stack do cenário, sem solução e sem testes de avaliação.

| Cenário | Pasta | Stack |
|---|---|---|
| TecnoIF 2026 (baixa) | `site-base/` | Vite + TypeScript + HTML/CSS |
| Labirinto Explorer (média) | `jogo-base/` | Vite + TypeScript + Canvas |
| ReservaFácil (alta) | `app-base/` | React + TypeScript + Hono + SQLite (`node:sqlite`) |

## Versões

- Node.js 22.17.0 (validado no host). Usar a mesma versão na imagem do contêiner.
- Dependências travadas por `package-lock.json`. Instalar com `npm ci`.

## SHA-256 dos lockfiles

| Starter | sha256 de `package-lock.json` |
|---|---|
| site-base | 010083ffc11a4a874ddb19fad1ca0e26a9a5c323d33cd2281cf53290db4f107e |
| jogo-base | d82f0e485c08e07e272e8420459ba799ddc0c4aa3881435c61a7dad0da641915 |
| app-base | 12d46e662b2db9ef6c9c8aae7b0a55069493b4a11bd6f91fe92c1d99e96656e2 |

Recalcular antes de cada coleta. Se o hash mudar, é desvio de protocolo.

## Decisões

- **SQLite no app-base:** usa `node:sqlite` (embutido no Node 22) em vez de `better-sqlite3`, para evitar compilação nativa dentro do contêiner. Decisão a aprovar pelo pesquisador antes da coleta.
- **Rede:** nenhuma instalação de pacotes durante a rodada. As dependências vêm pré-instaladas no starter ou na imagem. Política de npm a decidir (§7.10 item 4).

## Verificação

`npm run build` concluiu com exit 0 nos três starters.
