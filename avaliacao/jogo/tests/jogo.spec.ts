import { test } from '@playwright/test';
import { avaliar, localstorageTexto } from '../../shared/helpers.mjs';

// O mapa do jogo e deterministico, mas o enunciado NAO fixa o layout nem a
// interface. Assim, os criterios de estado (J03-J07, J09, J10) sao avaliados
// por proxies observaveis (canvas + texto da pagina + localStorage). Ver
// avaliacao/METODOLOGIA.md. Os proxies sao deliberadamente conservadores e
// serao validados contra uma implementacao de referencia.

async function resumoCanvas(page) {
  return page.evaluate(() => {
    const canvas = document.querySelector('canvas');
    if (!canvas) return null;
    const ctx = canvas.getContext('2d');
    if (!ctx) return null;
    const largura = canvas.width;
    const altura = canvas.height;
    const dados = ctx.getImageData(0, 0, largura, altura).data;
    const passo = 4 * Math.max(1, Math.floor((largura * altura) / 800));
    const cores = new Set();
    let soma = 0;
    for (let i = 0; i + 3 < dados.length; i += passo) {
      cores.add(`${dados[i]},${dados[i + 1]},${dados[i + 2]},${dados[i + 3]}`);
      soma += dados[i] + dados[i + 1] + dados[i + 2];
    }
    return { largura, altura, cores: cores.size, soma };
  });
}

async function teclar(page, tecla, vezes = 1) {
  for (let i = 0; i < vezes; i += 1) {
    await page.keyboard.down(tecla);
    await page.waitForTimeout(90);
    await page.keyboard.up(tecla);
    await page.waitForTimeout(90);
  }
}

async function focarCanvas(page) {
  const canvas = page.locator('canvas').first();
  if (await canvas.count()) await canvas.click();
  await page.waitForTimeout(300);
}

async function texto(page) {
  return (await page.locator('body').innerText()).toLowerCase();
}

test('J01 - projeto abre e desenha o tabuleiro', async ({ page }) => {
  await avaliar('J01_canvas', async () => {
    await page.goto('/', { waitUntil: 'load' });
    await page.waitForTimeout(800);
    const resumo = await resumoCanvas(page);
    if (!resumo) throw new Error('elemento canvas ausente');
    if (resumo.cores < 2) throw new Error('canvas uniforme (nada desenhado)');
    return `canvas ${resumo.largura}x${resumo.altura} com ${resumo.cores} cores`;
  });
});

test('J02 - movimento pelas quatro direcoes', async ({ page }) => {
  await avaliar('J02', async () => {
    await page.goto('/');
    await focarCanvas(page);
    const direcoes = ['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'];
    let moveram = 0;
    for (const tecla of direcoes) {
      const antes = await resumoCanvas(page);
      await teclar(page, tecla);
      const depois = await resumoCanvas(page);
      if (antes && depois && antes.soma !== depois.soma) moveram += 1;
    }
    if (moveram < 2) throw new Error(`apenas ${moveram}/4 direcoes alteraram o quadro`);
    return `${moveram}/4 direcoes alteraram o quadro`;
  });
});

test('J03 - paredes impedem deslocamento (proxy)', async ({ page }) => {
  await avaliar('J03', async () => {
    await page.goto('/');
    await focarCanvas(page);
    // Pressionar a mesma direcao repetidamente deve estabilizar (bloqueio por
    // parede ou borda), em vez de mudar o quadro indefinidamente.
    let anterior = await resumoCanvas(page);
    let estavel = false;
    for (let i = 0; i < 14; i += 1) {
      await teclar(page, 'ArrowLeft');
      const atual = await resumoCanvas(page);
      if (anterior && atual && anterior.soma === atual.soma) {
        estavel = true;
        break;
      }
      anterior = atual;
    }
    if (!estavel) throw new Error('quadro nunca estabilizou ao mover contra a borda/parede');
    return 'movimento estabilizou (bloqueio observado)';
  });
});

test('J04 - chaves coletadas e contabilizadas (proxy)', async ({ page }) => {
  await avaliar('J04', async () => {
    await page.goto('/');
    await focarCanvas(page);
    const t = await texto(page);
    const storage = (await localstorageTexto(page)).toLowerCase();
    const mencionaChave = /chave|key/.test(t) || /chave|key/.test(storage);
    if (!mencionaChave) throw new Error('nenhuma mencao a chaves encontrada na interface');
    // Executa uma caminhada curta tentando coletar; aceita se um contador mudou
    // ou se a interface declara a existencia/contagem de chaves.
    const antes = await resumoCanvas(page);
    for (const tecla of ['ArrowRight', 'ArrowDown', 'ArrowLeft', 'ArrowUp', 'ArrowRight']) {
      await teclar(page, tecla);
    }
    const depois = await resumoCanvas(page);
    return `mencao_a_chave=sim quadro_mudou=${antes && depois ? antes.soma !== depois.soma : 'n/d'}`;
  });
});

test('J05 - saida so permite vitoria apos tres chaves (proxy)', async ({ page }) => {
  await avaliar('J05', async () => {
    await page.goto('/');
    await page.waitForTimeout(400);
    const t = await texto(page);
    const temSaida = /sa[ií]da|exit/.test(t);
    const temChave = /chave|key/.test(t);
    if (!temSaida || !temChave) {
      throw new Error('interface nao declara saida e chaves (proxy estrutural)');
    }
    return 'interface declara saida e chaves';
  });
});

test('J06 - colisoes com inimigos reduzem vidas (proxy)', async ({ page }) => {
  await avaliar('J06', async () => {
    await page.goto('/');
    await page.waitForTimeout(400);
    const t = await texto(page);
    if (!/vida|life/.test(t) || !/\d/.test(t)) {
      throw new Error('interface nao exibe indicador de vidas numerico');
    }
    return 'indicador de vidas presente';
  });
});

test('J07 - pontuacao e cronometro evoluem (proxy)', async ({ page }) => {
  await avaliar('J07', async () => {
    await page.goto('/');
    await page.waitForTimeout(400);
    const t1 = await texto(page);
    const c1 = await resumoCanvas(page);
    await page.waitForTimeout(1500);
    const t2 = await texto(page);
    const c2 = await resumoCanvas(page);
    const textoMudou = t1 !== t2;
    const quadroMudou = c1 && c2 ? c1.soma !== c2.soma : false;
    if (!textoMudou && !quadroMudou) throw new Error('nada evoluiu em 1,5s (sem cronometro/animacao)');
    return `texto_mudou=${textoMudou} quadro_mudou=${quadroMudou}`;
  });
});

test('J08 - pausa congela tempo e movimentacao', async ({ page }) => {
  await avaliar('J08', async () => {
    await page.goto('/');
    await focarCanvas(page);
    await teclar(page, 'p');
    await page.waitForTimeout(200);
    const antes = await resumoCanvas(page);
    await teclar(page, 'ArrowRight');
    await page.waitForTimeout(700);
    const depois = await resumoCanvas(page);
    if (!antes || !depois) throw new Error('canvas ausente');
    if (antes.soma !== depois.soma) throw new Error('movimentacao ocorreu durante a pausa');
    return 'quadro imovel durante a pausa';
  });
});

test('J09 - reinicio restaura estado inicial (proxy)', async ({ page }) => {
  await avaliar('J09', async () => {
    await page.goto('/');
    await focarCanvas(page);
    const inicial = await resumoCanvas(page);
    await teclar(page, 'ArrowRight', 3);
    await teclar(page, 'ArrowDown', 3);
    const movido = await resumoCanvas(page);
    // Tenta reiniciar por tecla 'r' ou botao textual.
    const botao = page
      .locator('button, a, [role="button"]')
      .filter({ hasText: /reinici|restart|novo jogo/i })
      .first();
    if (await botao.count()) {
      await botao.click();
    } else {
      await teclar(page, 'r');
    }
    await page.waitForTimeout(600);
    const apos = await resumoCanvas(page);
    if (!inicial || !movido || !apos) throw new Error('canvas ausente');
    if (inicial.soma === movido.soma) throw new Error('o jogo nao respondeu ao movimento (nao ha o que reiniciar)');
    const restaurou = Math.abs(apos.soma - inicial.soma) < Math.abs(apos.soma - movido.soma) + 1;
    if (!restaurou) throw new Error('reinicio nao aproximou o quadro do estado inicial');
    return 'reinicio aproximou do estado inicial';
  });
});

test('J10 - recorde persiste (proxy)', async ({ page }) => {
  await avaliar('J10', async () => {
    await page.goto('/');
    await focarCanvas(page);
    for (const tecla of ['ArrowRight', 'ArrowDown', 'ArrowRight', 'ArrowUp', 'ArrowLeft']) {
      await teclar(page, tecla);
    }
    await page.waitForTimeout(400);
    const t = await texto(page);
    const storage = (await localstorageTexto(page)).toLowerCase();
    const temRecorde = /recorde|record|melhor|best/.test(t) || /recorde|record|best|high/.test(storage);
    if (!temRecorde) throw new Error('nenhum indicador de recorde encontrado');
    return 'indicador de recorde presente';
  });
});
