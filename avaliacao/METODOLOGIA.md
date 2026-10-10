# Metodologia do instrumento de avaliacao

Documento de apoio ao avaliador independente (`avaliacao/`). Registra as
decisoes de instrumentacao congeladas em 10/10/2026, aprovadas pela
pesquisadora (o guia do orientador e o plano v2 silenciam nestes pontos).

## Principio

Os testes verificam **comportamento observavel** (plano 7.10 item 10; guia
secao 08) e **nao dependem de nomes internos de classes, arquivos ou rotas**
que o enunciado nao exige. Um criterio aprovado vale 1; reprovado vale 0;
**nao observado vale `null`** (marcador `NAO_OBSERVADO`) e sai do denominador,
nunca vira zero.

O avaliador roda em um contêiner a partir da imagem `tcc-harnesses:v1`
(Node 22.23.3), com o repositorio e o cache de browsers do host montados. O
cenario `app` usa `node:sqlite`, que exige Node 22.

## Niveis de teste

| Nivel | Implementacao |
|---|---|
| Build | `npm run build` no snapshot (criterios S01/J01/A01, parte `_build`) |
| E2E | Playwright 1.64.0, Chromium 1248 (todos os criterios de comportamento) |
| Integracao/backend | Playwright `request` sobre as rotas DESCOBERTAS (app: A08, A09) |
| Estatico | O `npm run build` dos starters roda `tsc --noEmit` |

**Nota sobre Vitest.** Os starters/planos citam testes unitarios com Vitest.
Como o enunciado nao fixa caminhos nem assinaturas de modulos, testes
unitarios por importacao direta dependeriam de convencoes nao exigidas e
introduziriam vies. A verificacao de regras/estado e feita por E2E. Desvio
registrado.

## Criterios por cenario

### Site (S01-S10)
Comportamento observado no DOM/localStorage, com heuristicas tolerantes:
- S03 exige as tres trilhas (IA/Web/Seguranca) no texto e >= 6 itens de
  palestra visiveis (elementos com horario/trilha).
- S04 exige um controle de filtro por trilha e que a contagem de palestras
  visiveis diminua ao aplica-lo (mantendo >= 1).

### Jogo (J01-J10)
O mapa e determinista, mas o enunciado **nao fixa o layout nem a interface**.
A suite **descobre um objeto de estado do jogo em `window`** (ex.:
`window.__labirinto` com `jogador`, `chaves`, `vidas`, `pontos`, `tempo`,
`estado`, `saidaLiberada`, `recorde`, `posicoesChaves`):
- J01/J02: canvas desenha; movimento (por estado ou, na ausencia, por quadro).
- J03/J04/J05/J06/J09: verificados no estado (bloqueio, coleta, saida
  liberada, vidas, reinicio). **Sem estado, viram `null`.**
- J07: cronometro/pontuacao evolui (estado ou texto).
- J08: pausa congela jogador e tempo (estado ou quadro).
- J10: recorde persiste (estado/localStorage apos recarga).
A convencao do objeto de estado e uma **expectativa do instrumento**; sem ela,
os criterios de estado sao reportados como nao observados. A ratificar.

### App (A01-A10)
Rotas e credenciais **nao** sao fixadas. O avaliador:
1. sobe o app descobrindo o script (`dev/start/serve/preview`) no
   `package.json` e testando portas comuns, passando `PORT`;
2. autentica por **registro ou login descobertos** na interface (e-mail unico
   por execucao; segundo usuario em contexto de navegador separado);
3. para A08/A09, **observa as rotas de API** usadas pela propria aplicacao e
   as reusa (`POST`) para enviar dados invalidos e duas requisicoes
   simultaneas.
Se o bootstrap (auth/criacao) nao for descoberto, o criterio vira
`NAO_OBSERVADO` (null). Alternativa a ratificar: fixar um contrato minimo de
rotas/credenciais e divulga-lo no README do starter, igual para todas as
condicoes — nao adotada para nao introduzir requisito ausente no prompt.

## Fluxo agregador

`record.mjs` grava uma "parte" por verificacao; `collect.mjs` agrega por
criterio (0 se alguma parte falha, 1 se todas passam, null se nenhuma parte);
`score.py` calcula:
- **B (qualidade de referencia):** todos os criterios, ponderados;
- **A (aderencia):** so os criterios do `mapeamento-criterio-prompt.json`.

## Status da validacao (10/10/2026)

Suites executadas contra implementacoes de referencia em `avaliacao/_referencia/`
(fora dos starters, fora do alcance do agente), no contêiner Node 22:
**site 10/10, jogo 10/10, app 10/10.** Correcoes decorrentes: `vite-env.d.ts`
nos starters, normalizacao de booleanos no `collect.mjs`, libs do Chromium na
imagem, e pinagem das dependencias do avaliador por lockfile.

## Limitacoes declaradas

- O objeto de estado do jogo e as rotas descobertas do app podem produzir
  `null` ou falso negativo em solucoes muito distintas das referencias; o `n`
  real por criterio e reportado e entra na analise de sensibilidade.
