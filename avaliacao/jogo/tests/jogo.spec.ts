import { test } from '@playwright/test';
import { avaliar } from '../../shared/helpers.mjs';

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

async function teclar(page, tecla) {
  await page.keyboard.down(tecla);
  await page.waitForTimeout(120);
  await page.keyboard.up(tecla);
  await page.waitForTimeout(120);
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
    await page.locator('canvas').first().click();
    await page.waitForTimeout(300);
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

test('J08 - pausa congela tempo e movimentacao', async ({ page }) => {
  await avaliar('J08', async () => {
    await page.goto('/');
    await page.locator('canvas').first().click();
    await page.waitForTimeout(300);
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
