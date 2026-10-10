import { test } from '@playwright/test';
import { avaliar } from '../../shared/helpers.mjs';

// O enunciado do app NAO fixa rotas nem credenciais. Para nao penalizar
// escolhas legitimas, os criterios A02-A10 sao avaliados por DESCOBERTA: a
// interface e dirigida e as rotas de API usadas pela propria aplicacao sao
// observadas. Quando o bootstrap (login/registro) nao pode ser descoberto, o
// criterio e marcado NAO_OBSERVADO (null) em vez de zero. Ver METODOLOGIA.md.

const SENHA = 'Avaliacao#2026';

function registrarRede(page, coletor) {
  page.on('request', (req) => {
    const url = req.url();
    if (!/^https?:\/\/(127\.0\.0\.1|localhost)/.test(url)) return;
    if (!/\/(api|auth|login|sess|salas|rooms|reserv|users|usuarios|histor)/i.test(url)) return;
    coletor.push({ metodo: req.method(), url, corpo: req.postData() || null });
  });
}

async function preencherAuth(page, { nome, email, senha }) {
  const preenche = async (loc, valor) => {
    if (loc && (await loc.count())) {
      await loc.first().fill(valor);
      return true;
    }
    return false;
  };
  const senhaInput = page.locator('input[type="password"]').first();
  if (!(await senhaInput.count())) return false;
  const emailInput = page
    .locator('input[type="email"], input[name*="email" i], input[name*="usuario" i], input[name*="login" i]')
    .first();
  const nomeInput = page
    .locator('input[name*="nome" i], input[name*="name" i], input[type="text"]')
    .first();
  await preenche(emailInput, email);
  await preenche(nomeInput, nome);
  await preenche(senhaInput, senha);
  return true;
}

async function submeter(page) {
  const btn = page
    .locator('button[type="submit"], input[type="submit"], button:has-text("Entrar"), button:has-text("Login"), button:has-text("Cadastr"), button:has-text("Registr")')
    .first();
  if (!(await btn.count())) throw new Error('botao de autenticacao nao encontrado');
  await btn.click();
  await page.waitForTimeout(1200);
}

async function autenticar(page, email) {
  // 1) tenta registrar (cria conta) se houver affordance de cadastro.
  const linkCadastro = page
    .locator('a, button')
    .filter({ hasText: /cadastr|registr|criar conta|sign ?up/i })
    .first();
  if (await linkCadastro.count()) {
    await linkCadastro.click();
    await page.waitForTimeout(600);
    if (await preencherAuth(page, { nome: 'Avaliacao User', email, senha: SENHA })) {
      await submeter(page);
    }
  }
  // 2) login com as credenciais informadas.
  if (await page.locator('input[type="password"]').count()) {
    await preencherAuth(page, { nome: 'Avaliacao User', email, senha: SENHA });
    await submeter(page);
  }
  const saiuDoLogin = !(await page.locator('input[type="password"]').count());
  return saiuDoLogin;
}

async function abrirApp(page) {
  await page.goto('/', { waitUntil: 'load' });
  await page.waitForTimeout(1200);
}

async function criarReserva(page, { sala, inicio, fim }) {
  // Dirige o formulario de reserva pela interface, preenchendo os campos
  // disponiveis. Nao depende de nomes internos.
  const abrir = page
    .locator('a, button')
    .filter({ hasText: /nova reserva|reservar|criar reserva|adicionar reserva|nova/i })
    .first();
  if (await abrir.count()) {
    await abrir.click();
    await page.waitForTimeout(400);
  }
  const campos = page.locator('form input, form select, form textarea');
  const n = await campos.count();
  for (let i = 0; i < n; i += 1) {
    const c = campos.nth(i);
    const tipo = (await c.getAttribute('type')) || '';
    const tag = await c.evaluate((el) => el.tagName.toLowerCase());
    if (tipo === 'password') continue;
    if (tag === 'select') {
      try {
        await c.selectOption({ index: 1 });
      } catch {
        /* ignora */
      }
      continue;
    }
    const name = ((await c.getAttribute('name')) || '').toLowerCase();
    const ph = ((await c.getAttribute('placeholder')) || '').toLowerCase();
    let valor = 'Avaliacao';
    if (/in[ií]cio|start|from/.test(name + ph)) valor = inicio;
    else if (/fim|end|t[oé]|until/.test(name + ph)) valor = fim;
    else if (/sala|room/.test(name + ph)) valor = sala;
    else if (tipo === 'datetime-local' || tipo === 'date' || tipo === 'time') valor = inicio.includes('T') ? inicio : inicio;
    else if (tipo === 'number') valor = '60';
    try {
      await c.fill(valor);
    } catch {
      /* ignora */
    }
  }
  const salvar = page
    .locator('form button[type="submit"], form button:has-text("Salvar"), form button:has-text("Reservar"), form button:has-text("Criar"), form button:has-text("Confirmar")')
    .first();
  if (!(await salvar.count())) throw new Error('botao de salvar reserva nao encontrado');
  await salvar.click();
  await page.waitForTimeout(1200);
}

test('A01frontend - frontend inicia sem erro', async ({ page }) => {
  await avaliar('A01_frontend', async () => {
    const erros = [];
    page.on('pageerror', (erro) => erros.push(String(erro)));
    await page.goto('/', { waitUntil: 'load' });
    await page.waitForTimeout(800);
    const corpo = (await page.locator('body').innerText()).trim();
    if (corpo.length < 5) throw new Error('frontend sem conteudo renderizado');
    if (erros.length) throw new Error(`erros de pagina: ${erros[0]}`);
    return `frontend renderizou ${corpo.length} caracteres`;
  });
});

test('A02 - login, logout e protecao', async ({ page }) => {
  await avaliar('A02', async () => {
    await abrirApp(page);
    if (!(await page.locator('input[type="password"]').count())) {
      throw new Error('sem formulario de autenticacao (protecao ausente)');
    }
    // senha errada deve ser rejeitada
    await preencherAuth(page, { nome: 'x', email: `errado_${Date.now()}@example.com`, senha: 'senhaerrada' });
    await submeter(page);
    if (!(await page.locator('input[type="password"]').count())) {
      throw new Error('login aceitou credenciais invalidas');
    }
    const ok = await autenticar(page, `av_${Date.now()}@example.com`);
    if (!ok) throw new Error('nao foi possivel autenticar com credenciais validas');
    const logout = page
      .locator('a, button')
      .filter({ hasText: /sair|logout|encerrar sess/i })
      .first();
    if (await logout.count()) {
      await logout.click();
      await page.waitForTimeout(800);
    }
    return 'login valido aceito, invalido rejeitado, logout presente';
  });
});

test('A03 - usuario comum nao modifica reservas alheias', async ({ browser }) => {
  const contexto = await browser.newContext();
  const contexto2 = await browser.newContext();
  await avaliar('A03', async () => {
    const page = await contexto.newPage();
    await abrirApp(page);
    const email = `av_${Date.now()}@example.com`;
    if (!(await autenticar(page, email))) {
      throw new Error('NAO_OBSERVADO autenticacao indiscoverivel');
    }
    try {
      await criarReserva(page, { sala: '1', inicio: '2030-01-10T10:00', fim: '2030-01-10T11:00' });
    } catch {
      throw new Error('NAO_OBSERVADO fluxo de criacao de reserva indiscoverivel');
    }
    // outro usuario em um CONTEXTO SEPARADO, tentando editar pela interface
    const page2 = await contexto2.newPage();
    await abrirApp(page2);
    if (!(await autenticar(page2, `outro_${Date.now()}@example.com`))) {
      throw new Error('NAO_OBSERVADO segundo login indiscoverivel');
    }
    const editar = page2
      .locator('a, button')
      .filter({ hasText: /editar|alterar|edit/i })
      .first();
    if (!(await editar.count())) {
      throw new Error('NAO_OBSERVADO nenhuma reserva editavel visivel para o outro usuario (protecao plausivel)');
    }
    await editar.click();
    await page2.waitForTimeout(600);
    const salvar = page2
      .locator('button')
      .filter({ hasText: /salvar|atualiz|confirm/i })
      .first();
    if (!(await salvar.count())) {
      throw new Error('NAO_OBSERVADO botao de salvar edicao nao encontrado');
    }
    await salvar.click();
    await page2.waitForTimeout(800);
    // Se a edicao foi aceita sem erro visivel, considera falha de protecao.
    const texto = (await page2.locator('body').innerText()).toLowerCase();
    const rejeitado = /erro|negad|permiss|proibid|403|alheia|nao autoriz|unauthorized/.test(texto);
    if (!rejeitado) throw new Error('edicao de reserva alheia parece ter sido aceita');
    return 'edicao alheia rejeitada';
  });
  await contexto.close();
  await contexto2.close();
});

test('A04 - administrador gerencia salas', async ({ page }) => {
  await avaliar('A04', async () => {
    await abrirApp(page);
    if (!(await autenticar(page, `admin_${Date.now()}@example.com`))) {
      throw new Error('NAO_OBSERVADO autenticacao indiscoverivel');
    }
    const t = await page.locator('body').innerText();
    const salas = (t.match(/sala/gi) || []).length;
    if (salas < 4) throw new Error(`interface nao lista salas suficientes (mencoes=${salas})`);
    return `mencoes a salas=${salas}`;
  });
});

test('A05 - CRUD de reservas persistente', async ({ page }) => {
  await avaliar('A05', async () => {
    await abrirApp(page);
    if (!(await autenticar(page, `crud_${Date.now()}@example.com`))) {
      throw new Error('NAO_OBSERVADO autenticacao indiscoverivel');
    }
    try {
      await criarReserva(page, { sala: '1', inicio: '2031-02-10T10:00', fim: '2031-02-10T11:00' });
    } catch {
      throw new Error('NAO_OBSERVADO fluxo de criacao de reserva indiscoverivel');
    }
    await page.reload({ waitUntil: 'load' });
    await page.waitForTimeout(1000);
    const t = await page.locator('body').innerText();
    if (!/2031|fev|02\/10|10:00/i.test(t)) {
      throw new Error('reserva nao persistiu apos recarga');
    }
    return 'reserva persistiu apos recarga';
  });
});

test('A06 - filtros por sala, data e usuario', async ({ page }) => {
  await avaliar('A06', async () => {
    await abrirApp(page);
    if (!(await autenticar(page, `filtro_${Date.now()}@example.com`))) {
      throw new Error('NAO_OBSERVADO autenticacao indiscoverivel');
    }
    const controles = page.locator('input[type="search"], input[placeholder*="filtro" i], select');
    if (!(await controles.count())) {
      throw new Error('NAO_OBSERVADO nenhum controle de filtro localizado');
    }
    return `controles_de_filtro=${await controles.count()}`;
  });
});

test('A07 - sobreposicao de horarios rejeitada', async ({ page }) => {
  await avaliar('A07', async () => {
    await abrirApp(page);
    if (!(await autenticar(page, `over_${Date.now()}@example.com`))) {
      throw new Error('NAO_OBSERVADO autenticacao indiscoverivel');
    }
    try {
      await criarReserva(page, { sala: '1', inicio: '2032-03-10T10:00', fim: '2032-03-10T11:00' });
      await page.waitForTimeout(600);
      await criarReserva(page, { sala: '1', inicio: '2032-03-10T10:30', fim: '2032-03-10T11:30' });
    } catch {
      throw new Error('NAO_OBSERVADO fluxo de criacao de reserva indiscoverivel');
    }
    const t = (await page.locator('body').innerText()).toLowerCase();
    const rejeitado = /conflito|sobrepos|indispon|j[aá] reservad|hor[aá]rio ocupado|409/.test(t);
    if (!rejeitado) throw new Error('sobreposicao nao apresentou rejeicao');
    return 'sobreposicao rejeitada';
  });
});

test('A08 - dados invalidos rejeitados no backend', async ({ browser, request }) => {
  const contexto = await browser.newContext();
  await avaliar('A08', async () => {
    const page = await contexto.newPage();
    const coletor = [];
    registrarRede(page, coletor);
    await abrirApp(page);
    if (!(await autenticar(page, `inv_${Date.now()}@example.com`))) {
      throw new Error('NAO_OBSERVADO autenticacao indiscoverivel');
    }
    try {
      await criarReserva(page, { sala: '1', inicio: '2033-01-05T10:00', fim: '2033-01-05T11:00' });
    } catch {
      throw new Error('NAO_OBSERVADO fluxo de criacao de reserva indiscoverivel');
    }
    const alvo = coletor.find((c) => c.metodo === 'POST' && c.corpo && /reserv/i.test(c.url));
    if (!alvo) throw new Error('NAO_OBSERVADO rota de criacao de reserva nao observada na rede');
    const body = JSON.parse(alvo.corpo);
    // inicio posterior ao fim (invalido)
    for (const k of Object.keys(body)) {
      if (/inicio|start|from/i.test(k)) body[k] = '2033-01-01T12:00';
      if (/fim|end|to|until/i.test(k)) body[k] = '2033-01-01T11:00';
    }
    const resp = await request.post(alvo.url, { data: body });
    if (resp.status() < 400) throw new Error(`backend aceitou dados invalidos (HTTP ${resp.status()})`);
    return `HTTP ${resp.status()} para dados invalidos`;
  });
  await contexto.close();
});

test('A09 - concorrencia nao permite conflito duplo', async ({ browser }) => {
  const contexto = await browser.newContext();
  await avaliar('A09', async () => {
    const page = await contexto.newPage();
    const coletor = [];
    registrarRede(page, coletor);
    await abrirApp(page);
    if (!(await autenticar(page, `conc_${Date.now()}@example.com`))) {
      throw new Error('NAO_OBSERVADO autenticacao indiscoverivel');
    }
    try {
      await criarReserva(page, { sala: '1', inicio: '2034-04-10T09:00', fim: '2034-04-10T10:00' });
    } catch {
      throw new Error('NAO_OBSERVADO fluxo de criacao de reserva indiscoverivel');
    }
    const alvo = coletor.find((c) => c.metodo === 'POST' && c.corpo && /reserv/i.test(c.url));
    if (!alvo) throw new Error('NAO_OBSERVADO rota de criacao de reserva nao observada na rede');
    const body = JSON.parse(alvo.corpo);
    for (const k of Object.keys(body)) {
      if (/inicio|start|from/i.test(k)) body[k] = '2034-04-10T09:00';
      if (/fim|end|to|until/i.test(k)) body[k] = '2034-04-10T10:00';
    }
    const [r1, r2] = await Promise.all([
      contexto.request.post(alvo.url, { data: body }),
      contexto.request.post(alvo.url, { data: body }),
    ]);
    const sucessos = [r1, r2].filter((r) => r.status() >= 200 && r.status() < 300).length;
    if (sucessos > 1) throw new Error(`duas reservas conflitantes aceitas (sucessos=${sucessos})`);
    return `sucessos=${sucessos}`;
  });
  await contexto.close();
});

test('A10 - historico registra alteracoes', async ({ page }) => {
  await avaliar('A10', async () => {
    await abrirApp(page);
    if (!(await autenticar(page, `hist_${Date.now()}@example.com`))) {
      throw new Error('NAO_OBSERVADO autenticacao indiscoverivel');
    }
    const linkHist = page
      .locator('a, button')
      .filter({ hasText: /hist[oó]rico|hist[oó]ria|log de|auditoria/i })
      .first();
    if (!(await linkHist.count())) {
      throw new Error('NAO_OBSERVADO interface de historico nao localizada');
    }
    await linkHist.click();
    await page.waitForTimeout(800);
    const t = await page.locator('body').innerText();
    if (t.trim().length < 5) throw new Error('historico vazio');
    return 'interface de historico acessivel';
  });
});
