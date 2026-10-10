import { registrar } from './record.mjs';

export async function avaliar(id, fn) {
  try {
    const motivo = await fn();
    registrar(id, 1, typeof motivo === 'string' ? motivo : 'ok');
  } catch (erro) {
    const motivo = erro && erro.message ? erro.message : String(erro);
    // "Nao observado" (ex.: bootstrap indiscoverivel) vira null, nunca zero:
    // o criterio sai do denominador em vez de ser penalizado (plano 7.14).
    if (motivo.startsWith('NAO_OBSERVADO')) {
      registrar(id, null, motivo.replace('NAO_OBSERVADO', '').trim());
      return;
    }
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

// Localiza a MENOR area (section/div/ul/...) cujo texto contenha algum termo,
// para isolar programacao/palestrantes sem depender de nomes internos.
export async function localizarArea(page, termos) {
  const areas = page.locator('section, article, div, ul, ol');
  const total = await areas.count();
  let melhor = null;
  let melhorTamanho = Number.POSITIVE_INFINITY;
  for (let i = 0; i < total; i += 1) {
    const area = areas.nth(i);
    if (!(await area.isVisible().catch(() => false))) continue;
    let texto = '';
    try {
      texto = await area.innerText({ timeout: 400 });
    } catch {
      continue;
    }
    if (texto.trim().length < 30) continue;
    const minusculo = texto.toLowerCase();
    if (termos.some((t) => minusculo.includes(t.toLowerCase()))) {
      if (texto.length < melhorTamanho) {
        melhorTamanho = texto.length;
        melhor = area;
      }
    }
  }
  return melhor;
}

// Conta itens repetidos dentro de um escopo, tentando seletores genericos em
// ordem de especificidade.
export async function contarItens(escopo) {
  const tentativas = [
    'article',
    'li',
    '[class*="palestra" i], [class*="talk" i], [class*="lecture" i]',
    '[class*="card" i]',
    'h3, h4',
  ];
  let melhor = 0;
  for (const seletor of tentativas) {
    const n = await escopo.locator(seletor).count();
    if (n > melhor) melhor = n;
    if (n >= 3) return n;
  }
  return melhor;
}

// Conta elementos visiveis que casam com o seletor (page-wide).
export async function contarVisiveis(page, seletor) {
  const loc = page.locator(seletor);
  const total = await loc.count();
  let n = 0;
  for (let i = 0; i < total; i += 1) {
    if (await loc.nth(i).isVisible().catch(() => false)) n += 1;
  }
  return n;
}

function escapeRegex(texto) {
  return String(texto).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// Aplica um filtro cujo rotulo contenha `texto` como palavra. Suporta
// botao/link/label ou option de select.
export async function aplicarFiltro(page, texto) {
  const re = new RegExp(`\\b${escapeRegex(texto)}\\b`, 'i');
  const alvo = page
    .locator('button, a, [role="button"], label, option')
    .filter({ hasText: re })
    .first();
  if (await alvo.count()) {
    const tag = await alvo.evaluate((el) => el.tagName.toLowerCase());
    if (tag === 'option') {
      const valor = await alvo.getAttribute('value');
      const select = page.locator('select').first();
      await select.selectOption(valor != null ? valor : { label: texto });
    } else {
      await alvo.click();
    }
    await page.waitForTimeout(600);
    return true;
  }
  const radio = page.locator('input[type="radio"], input[type="checkbox"]').first();
  if (await radio.count()) {
    await radio.check();
    await page.waitForTimeout(400);
    return true;
  }
  return false;
}

// Rotulo textual do harness (para notas de diagnostico).
export function diagnostico(nome, valor) {
  return `${nome}=${valor}`;
}
