import { test } from '@playwright/test';
import { avaliar } from '../../shared/helpers.mjs';

test('A01frontend - frontend inicia sem erro', async ({ page }) => {
  await avaliar('A01_frontend', async () => {
    const erros = [];
    page.on('pageerror', (erro) => erros.push(String(erro)));
    await page.goto('/', { waitUntil: 'load' });
    await page.waitForTimeout(600);
    const corpo = (await page.locator('body').innerText()).trim();
    if (corpo.length < 5) throw new Error('frontend sem conteudo renderizado');
    if (erros.length) throw new Error(`erros de pagina: ${erros[0]}`);
    return `frontend renderizou ${corpo.length} caracteres`;
  });
});
