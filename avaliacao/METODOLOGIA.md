# Metodologia do instrumento de avaliacao

Documento de apoio ao avaliador independente (`avaliacao/`). Registra as
decisoes de instrumentacao congeladas em 10/10/2026, aprovadas pela
pesquisadora (o guia do orientador e o plano v2 silenciam nestes pontos).

## Principio

Os testes verificam **comportamento observavel** (plano 7.10 item 10; guia
secao 08) e **nao dependem de nomes internos de classes, arquivos ou rotas**
que o enunciado nao exige. Um criterio aprovado vale 1; reprovado vale 0;
**nao observado vale `null`** e sai do denominador (nunca vira zero).

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
introduziriam vies. A verificacao de regras/estado e feita por E2E; o requisito
de testabilidade do J-P3 e honrado por E2E determinada. Desvio registrado.

## Criterios por cenario

### Site (S01-S10)
Comportamento observado no DOM/localStorage. Heuristicas tolerantes:
- S03 exige as tres trilhas (IA/Web/Seguranca) no texto e >= 6 itens de
  palestra visiveis (elementos `article/li`/classe de card/palestra que
  contenham horario, "IA", "Web" ou "Seguranca").
- S04 exige um controle de filtro por trilha e que a contagem de palestras
  visiveis diminua ao aplica-lo (mantendo >= 1).

### Jogo (J01-J10)
O mapa e determinista, mas o enunciado **nao fixa o layout nem a interface**.
Por isso os criterios de estado sao avaliados por **proxies observaveis**
(canvas + texto da pagina + localStorage) e identificados como `(proxy)`:
- J03: movimento repetido contra a borda/parede estabiliza o quadro.
- J04: interface/`localStorage` declaram chaves e o quadro responde.
- J05/J06: interface declara saida/chaves e vidas numericas.
- J07: texto ou quadro evolui em 1,5 s (cronometro/animacao).
- J09: reinicio aproxima o quadro do estado inicial.
- J10: interface/`localStorage` expoem recorde.
Estes proxies sao conservadores e devem ser validados contra uma
implementacao de referencia antes da coleta definitiva.

### App (A01-A10)
Rotas e credenciais **nao** sao fixadas. O avaliador:
1. sobe o app descobrindo o script (`dev/start/serve/preview`) no
   `package.json` e testando portas comuns, passando `PORT`;
2. autentica por **registro ou login descobertos** na interface (e-mail unico
   por execucao);
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

## Limitacoes declaradas

- Proxies do jogo e descoberta do app podem produzir `null` ou falso
  negativo; o `n` real por criterio e reportado e o `n` nao observado entra na
  analise de sensibilidade (plano 9, item 8).
- O instrumento deve ser validado contra implementacoes de referencia antes do
  congelamento final e do reinicio do piloto (P9).
