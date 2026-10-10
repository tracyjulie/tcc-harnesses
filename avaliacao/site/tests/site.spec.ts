import { test } from '@playwright/test';
import { avaliar, localstorageTexto, contarOcorrencias, limparStorage, primeiro } from '../../shared/helpers.mjs';

const EMAIL = 'maria.avaliacao@example.com';
const NOME = 'Maria Avaliacao';

async function campoNome(page) {
  return primeiro(page, ['input[name*="nome" i]', 'input[type="text"]', 'input:not([type])']);
}

async function campoEmail(page) {
  return primeiro(page, ['input[type="email"]', 'input[name*="email" i]', 'input[name*="e-mail" i]']);
}

async function botaoEnviar(page) {
  return primeiro(page, [
    'button[type="submit"]',
    'input[type="submit"]',
    'button:has-text("Inscrev")',
    'button:has-text("Enviar")',
    'button:has-text("Cadastr")',
    'button:has-text("Confirmar")',
  ]);
}

async function escolherPalestra(page) {
  const select = page.locator('select').first();
  if (await select.count()) {
    const opcoes = await select.locator('option').count();
    if (opcoes > 1) {
      await select.selectOption({ index: 1 });
      return 'select';
    }
  }
  const radio = page.locator('input[type="radio"]').first();
  if (await radio.count()) {
    await radio.check();
    return 'radio';
  }
  const check = page.locator('input[type="checkbox"]').first();
  if (await check.count()) {
    await check.check();
    return 'checkbox';
  }
  return null;
}

async function preencherValido(page) {
  const nome = await campoNome(page);
  const email = await campoEmail(page);
  if (!nome || !email) throw new Error('campos de nome/e-mail nao encontrados');
  await nome.fill(NOME);
  await email.fill(EMAIL);
  const palestra = await escolherPalestra(page);
  if (!palestra) throw new Error('nenhum seletor de palestra encontrado');
}

async function enviar(page) {
  const botao = await botaoEnviar(page);
  if (!botao) throw new Error('botao de envio nao encontrado');
  await botao.click();
  await page.waitForTimeout(800);
}

test('S01open - projeto abre com conteudo', async ({ page }) => {
  await avaliar('S01_open', async () => {
    await page.goto('/', { waitUntil: 'load' });
    await page.waitForTimeout(500);
    const corpo = (await page.locator('body').innerText()).trim();
    if (corpo.length < 10) throw new Error('pagina vazia ou sem conteudo');
    return `conteudo com ${corpo.length} caracteres`;
  });
});

test('S02 - secoes navegaveis e semantica', async ({ page }) => {
  await avaliar('S02', async () => {
    await page.goto('/');
    const links = await page.locator('a[href^="#"], nav a, header a').count();
    const estruturais = await page.locator('main, nav, header, footer, section, article, h1, h2').count();
    if (links < 1 && estruturais < 2) throw new Error('sem navegacao nem estrutura semantica');
    return `links=${links} estruturais=${estruturais}`;
  });
});

test('S06 - formulario aceita inscricao valida', async ({ page }) => {
  await avaliar('S06', async () => {
    await page.goto('/');
    await limparStorage(page);
    await preencherValido(page);
    await enviar(page);
    const ocorrencias = await contarOcorrencias(page, EMAIL);
    if (ocorrencias < 1) throw new Error('inscricao valida nao foi persistida');
    return 'inscricao persistida';
  });
});

test('S07 - formulario rejeita entradas invalidas', async ({ page }) => {
  await avaliar('S07', async () => {
    await page.goto('/');
    await limparStorage(page);
    const nome = await campoNome(page);
    const email = await campoEmail(page);
    if (!nome || !email) throw new Error('campos nao encontrados');
    await nome.fill('ab');
    await email.fill('invalido');
    await enviar(page);
    const blob = await localstorageTexto(page);
    if (blob.includes('invalido')) throw new Error('entrada invalida foi persistida');
    const texto = await page.locator('body').innerText();
    const erroVisivel = /inv[aá]lido|erro|obrigat[oó]rio|m[ií]nimo|corrija/i.test(texto);
    return erroVisivel ? 'rejeitado com mensagem' : 'rejeitado sem persistir';
  });
});

test('S08 - inscricoes persistem apos recarga', async ({ page }) => {
  await avaliar('S08', async () => {
    await page.goto('/');
    await limparStorage(page);
    await preencherValido(page);
    await enviar(page);
    if ((await contarOcorrencias(page, EMAIL)) < 1) throw new Error('nao persistiu antes da recarga');
    await page.reload({ waitUntil: 'load' });
    await page.waitForTimeout(400);
    const persiste = (await contarOcorrencias(page, EMAIL)) >= 1
      || (await page.locator('body').innerText()).includes(NOME);
    if (!persiste) throw new Error('inscricao desapareceu apos recarga');
    return 'inscricao presente apos recarga';
  });
});

test('S09 - inscricoes repetidas sao bloqueadas', async ({ page }) => {
  await avaliar('S09', async () => {
    await page.goto('/');
    await limparStorage(page);
    await preencherValido(page);
    await enviar(page);
    await preencherValido(page);
    await enviar(page);
    const ocorrencias = await contarOcorrencias(page, EMAIL);
    if (ocorrencias > 1) throw new Error(`inscricao duplicada persistida (${ocorrencias} vezes)`);
    return `ocorrencias=${ocorrencias}`;
  });
});

test('S10 - layout utilizavel em 360/768/1440', async ({ page }) => {
  await avaliar('S10', async () => {
    const medidas = [];
    for (const largura of [360, 768, 1440]) {
      await page.setViewportSize({ width: largura, height: 800 });
      await page.goto('/');
      await page.waitForTimeout(300);
      const overflow = await page.evaluate(() => {
        const doc = document.documentElement;
        return doc.scrollWidth - doc.clientWidth;
      });
      if (overflow > 4) throw new Error(`transbordo horizontal em ${largura}px (${overflow})`);
      medidas.push(`${largura}px:ok`);
    }
    return medidas.join(' ');
  });
});
