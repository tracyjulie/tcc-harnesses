import { test } from '@playwright/test';
import { avaliar, localstorageTexto } from '../../shared/helpers.mjs';

// O enunciado nao fixa o mapa nem a interface. Para poder verificar estados
// (paredes, chaves, vidas, reinicio), a suite DESCOBRE um objeto de estado do
// jogo exposto em `window` (ex.: window.__labirinto com jogador/chaves/vidas).
// Sem esse objeto, os criterios de estado viram NAO_OBSERVADO (null), nunca
// zero. Ver avaliacao/METODOLOGIA.md.

async function estado(page) {
  return page.evaluate(() => {
    const w = window as any;
    const ok = (v) => v && typeof v === 'object' && ('jogador' in v || 'vidas' in v || 'pontos' in v);
    const nomes = ['__labirinto', '__game', '__jogo', 'game', 'jogo', 'labirinto'];
    for (const n of nomes) {
      if (ok(w[n])) { try { return JSON.parse(JSON.stringify(w[n])); } catch { /* */ } }
    }
    for (const k of Object.keys(w)) {
      if (ok(w[k])) { try { return JSON.parse(JSON.stringify(w[k])); } catch { /* */ } }
    }
    return null;
  });
}

async function resumoCanvas(page) {
  return page.evaluate(() => {
    const canvas = document.querySelector('canvas');
    if (!canvas) return null;
    const ctx = canvas.getContext('2d');
    if (!ctx) return null;
    const dados = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
    const passo = 4 * Math.max(1, Math.floor((canvas.width * canvas.height) / 800));
    const cores = new Set();
    let soma = 0;
    for (let i = 0; i + 3 < dados.length; i += passo) {
      cores.add(`${dados[i]},${dados[i + 1]},${dados[i + 2]},${dados[i + 3]}`);
      soma += dados[i] + dados[i + 1] + dados[i + 2];
    }
    return { largura: canvas.width, altura: canvas.height, cores: cores.size, soma };
  });
}

async function teclar(page, tecla, vezes = 1) {
  for (let i = 0; i < vezes; i += 1) {
    await page.keyboard.down(tecla);
    await page.waitForTimeout(80);
    await page.keyboard.up(tecla);
    await page.waitForTimeout(80);
  }
}

async function focarCanvas(page) {
  const canvas = page.locator('canvas').first();
  if (await canvas.count()) await canvas.click();
  await page.waitForTimeout(250);
}

async function navegar(page, alvo) {
  for (let i = 0; i < 90; i += 1) {
    const e = await estado(page);
    if (!e || !e.jogador) return false;
    const p = e.jogador;
    if (p.x === alvo.x && p.y === alvo.y) return true;
    let key;
    if (p.x !== alvo.x) key = p.x < alvo.x ? 'ArrowRight' : 'ArrowLeft';
    else key = p.y < alvo.y ? 'ArrowDown' : 'ArrowUp';
    await teclar(page, key);
    const e2 = await estado(page);
    if (e2 && e2.jogador && e2.jogador.x === p.x && e2.jogador.y === p.y) {
      const alt = p.y !== alvo.y
        ? (p.y < alvo.y ? 'ArrowDown' : 'ArrowUp')
        : (p.x < alvo.x ? 'ArrowRight' : 'ArrowLeft');
      await teclar(page, alt);
    }
  }
  return false;
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
    const e0 = await estado(page);
    if (e0 && e0.jogador) {
      const direcoes = ['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'];
      let moveram = 0;
      for (const tecla of direcoes) {
        const a = await estado(page);
        await teclar(page, tecla);
        const b = await estado(page);
        if (a && b && a.jogador && b.jogador
          && (a.jogador.x !== b.jogador.x || a.jogador.y !== b.jogador.y)) moveram += 1;
      }
      if (moveram < 2) throw new Error(`apenas ${moveram}/4 direcoes moveram o jogador`);
      return `${moveram}/4 direcoes moveram o jogador (estado)`;
    }
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

test('J03 - paredes impedem deslocamento', async ({ page }) => {
  await avaliar('J03', async () => {
    await page.goto('/');
    await focarCanvas(page);
    const e0 = await estado(page);
    if (!e0 || !e0.jogador) throw new Error('NAO_OBSERVADO objeto de estado do jogo indisponivel');
    // Move repetidamente para a esquerda ate estabilizar; nao pode sair do tabuleiro.
    let anterior = { ...e0.jogador };
    let estavel = false;
    for (let i = 0; i < 20; i += 1) {
      await teclar(page, 'ArrowLeft');
      const e = await estado(page);
      if (!e || !e.jogador) throw new Error('estado indisponivel durante o movimento');
      if (e.jogador.x < 0 || e.jogador.y < 0) throw new Error('jogador saiu do tabuleiro');
      if (e.jogador.x === anterior.x && e.jogador.y === anterior.y) { estavel = true; break; }
      anterior = { ...e.jogador };
    }
    if (!estavel) throw new Error('jogador nao foi bloqueado por parede/borda');
    return 'bloqueio por parede/borda observado no estado';
  });
});

test('J04 - chaves coletadas e contabilizadas', async ({ page }) => {
  await avaliar('J04', async () => {
    await page.goto('/');
    await focarCanvas(page);
    const e0 = await estado(page);
    if (!e0) throw new Error('NAO_OBSERVADO objeto de estado do jogo indisponivel');
    const lista = e0.posicoesChaves || (Array.isArray(e0.chaves) ? e0.chaves : null);
    const contagem = typeof e0.chaves === 'number' ? e0.chaves : null;
    if (!lista) throw new Error('NAO_OBSERVADO posicoes das chaves indisponiveis no estado');
    if (!lista.length) throw new Error('nenhuma chave restante no inicio');
    await navegar(page, lista[0]);
    const e1 = await estado(page);
    const depois = typeof e1.chaves === 'number' ? e1.chaves : contagem;
    if (contagem !== null && depois !== null && depois <= contagem) {
      throw new Error(`contagem de chaves nao aumentou (antes=${contagem}, depois=${depois})`);
    }
    return `chaves antes=${contagem} depois=${depois}`;
  });
});

test('J05 - saida so libera com tres chaves', async ({ page }) => {
  await avaliar('J05', async () => {
    await page.goto('/');
    await focarCanvas(page);
    const e = await estado(page);
    if (!e || typeof e.saidaLiberada !== 'boolean') {
      throw new Error('NAO_OBSERVADO objeto de estado sem saidaLiberada');
    }
    const chaves = typeof e.chaves === 'number' ? e.chaves : 0;
    if (chaves < 3 && e.saidaLiberada) throw new Error('saida liberada antes das tres chaves');
    return `chaves=${chaves} saidaLiberada=${e.saidaLiberada}`;
  });
});

test('J06 - colisoes com inimigos reduzem vidas', async ({ page }) => {
  await avaliar('J06', async () => {
    await page.goto('/');
    await focarCanvas(page);
    const e0 = await estado(page);
    if (!e0 || typeof e0.vidas !== 'number') {
      throw new Error('NAO_OBSERVADO objeto de estado sem vidas');
    }
    const inicial = e0.vidas;
    let atual = inicial;
    for (let i = 0; i < 12 && atual >= inicial; i += 1) {
      await page.waitForTimeout(1000);
      const e = await estado(page);
      if (e && typeof e.vidas === 'number') atual = e.vidas;
    }
    if (atual >= inicial) throw new Error(`vidas nao reduziram apos colisao (vidas=${atual})`);
    return `vidas ${inicial} -> ${atual}`;
  });
});

test('J07 - pontuacao e cronometro evoluem', async ({ page }) => {
  await avaliar('J07', async () => {
    await page.goto('/');
    await page.waitForTimeout(300);
    const e1 = await estado(page);
    const t1 = await page.locator('body').innerText();
    await page.waitForTimeout(1600);
    const e2 = await estado(page);
    const t2 = await page.locator('body').innerText();
    const cronometro = e1 && e2 && typeof e1.tempo === 'number' && typeof e2.tempo === 'number'
      ? e2.tempo > e1.tempo
      : t1 !== t2;
    if (!cronometro) throw new Error('cronometro/pontuacao nao evoluiu');
    return `tempo ${e1 && e1.tempo} -> ${e2 && e2.tempo}`;
  });
});

test('J08 - pausa congela tempo e movimentacao', async ({ page }) => {
  await avaliar('J08', async () => {
    await page.goto('/');
    await focarCanvas(page);
    await teclar(page, 'p');
    await page.waitForTimeout(300);
    const e1 = await estado(page);
    const antes = await resumoCanvas(page);
    await teclar(page, 'ArrowRight');
    await page.waitForTimeout(700);
    const e2 = await estado(page);
    const depois = await resumoCanvas(page);
    if (e1 && e2 && e1.jogador && e2.jogador) {
      if (e1.jogador.x !== e2.jogador.x || e1.jogador.y !== e2.jogador.y) {
        throw new Error('jogador se moveu durante a pausa');
      }
      if (typeof e1.tempo === 'number' && typeof e2.tempo === 'number' && e2.tempo !== e1.tempo) {
        throw new Error('tempo avancou durante a pausa');
      }
      return 'pausa congelou jogador e tempo';
    }
    if (!antes || !depois) throw new Error('canvas ausente');
    if (antes.soma !== depois.soma) throw new Error('movimentacao ocorreu durante a pausa');
    return 'quadro imovel durante a pausa';
  });
});

test('J09 - reinicio restaura estado inicial', async ({ page }) => {
  await avaliar('J09', async () => {
    await page.goto('/');
    await focarCanvas(page);
    const e0 = await estado(page);
    if (!e0 || !e0.jogador) throw new Error('NAO_OBSERVADO objeto de estado do jogo indisponivel');
    const inicio = { ...e0.jogador };
    await teclar(page, 'ArrowRight', 3);
    await teclar(page, 'ArrowDown', 3);
    const movido = await estado(page);
    const botao = page.locator('button, a, [role="button"]').filter({ hasText: /reinici|restart|novo jogo/i }).first();
    if (await botao.count()) await botao.click();
    else await teclar(page, 'r');
    await page.waitForTimeout(500);
    const apos = await estado(page);
    if (!apos || !apos.jogador) throw new Error('estado indisponivel apos reinicio');
    if (movido && movido.jogador && apos.jogador.x === inicio.x && apos.jogador.y === inicio.y) {
      return 'reinicio restaurou a posicao inicial';
    }
    throw new Error(`reinicio nao restaurou o estado (inicio=${inicio.x},${inicio.y})`);
  });
});

test('J10 - recorde persiste entre partidas', async ({ page }) => {
  await avaliar('J10', async () => {
    await page.goto('/');
    await focarCanvas(page);
    const e0 = await estado(page);
    const ls0 = (await localstorageTexto(page)).toLowerCase();
    if (!e0 || (e0.recorde === undefined && !/recorde|record/.test(ls0))) {
      throw new Error('NAO_OBSERVADO nenhum indicador de recorde (estado/localStorage)');
    }
    const r0 = e0.recorde ?? null;
    await page.reload({ waitUntil: 'load' });
    await page.waitForTimeout(600);
    const e1 = await estado(page);
    const ls1 = (await localstorageTexto(page)).toLowerCase();
    if (r0 !== null && e1 && e1.recorde !== undefined && e1.recorde !== r0) {
      throw new Error(`recorde nao persistiu (${r0} -> ${e1.recorde})`);
    }
    if (!/recorde|record/.test(ls1) && (e1 === null || e1.recorde === undefined)) {
      throw new Error('recorde nao persistiu apos recarga');
    }
    return `recorde=${r0} persistiu`;
  });
});
