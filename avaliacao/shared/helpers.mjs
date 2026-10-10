import { registrar } from './record.mjs';

export async function avaliar(id, fn) {
  try {
    const motivo = await fn();
    registrar(id, 1, typeof motivo === 'string' ? motivo : 'ok');
  } catch (erro) {
    const motivo = erro && erro.message ? erro.message : String(erro);
    registrar(id, 0, motivo);
  }
}

export async function localstorageTexto(page) {
  return page.evaluate(() => {
    const partes = [];
    for (let i = 0; i < localStorage.length; i += 1) {
      const chave = localStorage.key(i);
      partes.push(String(chave), String(localStorage.getItem(chave)));
    }
    return partes.join(' ');
  });
}

export async function contarOcorrencias(page, texto) {
  const blob = await localstorageTexto(page);
  return blob.split(texto).length - 1;
}

export async function limparStorage(page) {
  await page.evaluate(() => localStorage.clear());
}

export async function primeiro(page, seletores) {
  for (const seletor of seletores) {
    const loc = page.locator(seletor).first();
    if (await loc.count()) return loc;
  }
  return null;
}
