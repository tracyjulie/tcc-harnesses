import { Hono } from "hono";
import { serve } from "@hono/node-server";
import { serveStatic } from "@hono/node-server/serve-static";
import { getCookie, setCookie, deleteCookie } from "hono/cookie";
import { DatabaseSync } from "node:sqlite";
import { randomUUID, randomBytes, scryptSync, timingSafeEqual } from "node:crypto";

const db = new DatabaseSync(":memory:");
db.exec(`
  CREATE TABLE usuarios (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, email TEXT UNIQUE, senha TEXT, papel TEXT);
  CREATE TABLE salas (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, capacidade INTEGER);
  CREATE TABLE reservas (id INTEGER PRIMARY KEY AUTOINCREMENT, sala_id INTEGER, usuario_id INTEGER, inicio TEXT, fim TEXT, status TEXT DEFAULT 'ativa');
  CREATE TABLE historico (id INTEGER PRIMARY KEY AUTOINCREMENT, reserva_id INTEGER, usuario_id INTEGER, acao TEXT, detalhe TEXT, criado_em TEXT);
`);

function hashSenha(senha) {
  const salt = randomBytes(16).toString("hex");
  const hash = scryptSync(senha, salt, 64).toString("hex");
  return `${salt}:${hash}`;
}
function conferirSenha(senha, armazenado) {
  const [salt, hash] = String(armazenado).split(":");
  const tentativa = scryptSync(senha, salt, 64);
  const alvo = Buffer.from(hash, "hex");
  return tentativa.length === alvo.length && timingSafeEqual(tentativa, alvo);
}

db.prepare("INSERT INTO usuarios (nome,email,senha,papel) VALUES (?,?,?,?)")
  .run("Administrador", "admin@example.com", hashSenha("admin123"), "admin");
db.prepare("INSERT INTO usuarios (nome,email,senha,papel) VALUES (?,?,?,?)")
  .run("Usuario Padrao", "user@example.com", hashSenha("user123"), "usuario");
for (const [nome, cap] of [["Sala 1", 10], ["Sala 2", 20], ["Sala 3", 30], ["Sala 4", 40]]) {
  db.prepare("INSERT INTO salas (nome,capacidade) VALUES (?,?)").run(nome, cap);
}

const sessoes = new Map();

function usuarioAtual(c) {
  const token = getCookie(c, "token");
  if (!token || !sessoes.has(token)) return null;
  return db.prepare("SELECT id,nome,email,papel FROM usuarios WHERE id = ?").get(sessoes.get(token)) || null;
}

function validar(inicio, fim) {
  const i = new Date(inicio).getTime();
  const f = new Date(fim).getTime();
  if (Number.isNaN(i) || Number.isNaN(f)) return "Datas invalidas";
  if (!(i < f)) return "Horario inicial deve ser anterior ao final";
  const minutos = (f - i) / 60000;
  if (minutos < 30 || minutos > 120) return "Duracao deve ser entre 30 e 120 minutos";
  return null;
}

function conflito(salaId, inicio, fim) {
  const r = db.prepare(
    "SELECT id FROM reservas WHERE sala_id=? AND status='ativa' AND inicio < ? AND fim > ?",
  ).get(salaId, fim, inicio);
  return Boolean(r);
}

const app = new Hono();

app.post("/api/auth/registrar", async (c) => {
  const { nome, email, senha } = await c.req.json();
  if (!nome || !email || !senha) return c.json({ erro: "Dados obrigatorios" }, 400);
  try {
    const info = db.prepare("INSERT INTO usuarios (nome,email,senha,papel) VALUES (?,?,?,?)")
      .run(nome, email, hashSenha(senha), "usuario");
    const token = randomUUID();
    sessoes.set(token, Number(info.lastInsertRowid));
    setCookie(c, "token", token, { httpOnly: true, path: "/", sameSite: "Lax" });
    return c.json({ id: Number(info.lastInsertRowid), nome, email, papel: "usuario" }, 201);
  } catch {
    return c.json({ erro: "E-mail ja cadastrado" }, 409);
  }
});

app.post("/api/auth/login", async (c) => {
  const { email, senha } = await c.req.json();
  const u = db.prepare("SELECT * FROM usuarios WHERE email = ?").get(email);
  if (!u || !conferirSenha(senha, u.senha)) return c.json({ erro: "Credenciais invalidas" }, 401);
  const token = randomUUID();
  sessoes.set(token, u.id);
  setCookie(c, "token", token, { httpOnly: true, path: "/", sameSite: "Lax" });
  return c.json({ id: u.id, nome: u.nome, email: u.email, papel: u.papel });
});

app.post("/api/auth/logout", (c) => {
  const token = getCookie(c, "token");
  if (token) sessoes.delete(token);
  deleteCookie(c, "token", { path: "/" });
  return c.json({ ok: true });
});

app.get("/api/auth/eu", (c) => {
  const u = usuarioAtual(c);
  return u ? c.json(u) : c.json({ erro: "Nao autenticado" }, 401);
});

app.get("/api/salas", (c) => c.json(db.prepare("SELECT * FROM salas ORDER BY id").all()));

app.post("/api/salas", async (c) => {
  const u = usuarioAtual(c);
  if (!u) return c.json({ erro: "Nao autenticado" }, 401);
  if (u.papel !== "admin") return c.json({ erro: "Apenas administradores" }, 403);
  const { nome, capacidade } = await c.req.json();
  if (!nome) return c.json({ erro: "Nome obrigatorio" }, 400);
  const info = db.prepare("INSERT INTO salas (nome,capacidade) VALUES (?,?)").run(nome, capacidade || 0);
  return c.json({ id: Number(info.lastInsertRowid), nome, capacidade: capacidade || 0 }, 201);
});

app.get("/api/reservas", (c) => {
  const u = usuarioAtual(c);
  if (!u) return c.json({ erro: "Nao autenticado" }, 401);
  const linhas = db.prepare(
    `SELECT r.id, r.sala_id AS salaId, s.nome AS sala, r.inicio, r.fim, r.usuario_id AS usuarioId, us.nome AS usuario, r.status
     FROM reservas r JOIN salas s ON s.id=r.sala_id JOIN usuarios us ON us.id=r.usuario_id
     WHERE r.status='ativa' ORDER BY r.inicio`,
  ).all();
  return c.json(linhas);
});

app.post("/api/reservas", async (c) => {
  const u = usuarioAtual(c);
  if (!u) return c.json({ erro: "Nao autenticado" }, 401);
  const corpo = await c.req.json();
  const salaId = Number(corpo.salaId ?? corpo.sala);
  const { inicio, fim } = corpo;
  const erro = validar(inicio, fim);
  if (erro || !salaId) return c.json({ erro: erro || "Sala obrigatoria" }, 400);
  db.exec("BEGIN IMMEDIATE");
  try {
    if (conflito(salaId, inicio, fim)) {
      db.exec("ROLLBACK");
      return c.json({ erro: "Conflito de horario para a sala" }, 409);
    }
    const info = db.prepare("INSERT INTO reservas (sala_id,usuario_id,inicio,fim) VALUES (?,?,?,?)")
      .run(salaId, u.id, inicio, fim);
    db.prepare("INSERT INTO historico (reserva_id,usuario_id,acao,detalhe,criado_em) VALUES (?,?,?,?,?)")
      .run(Number(info.lastInsertRowid), u.id, "criacao", `Reserva ${inicio} - ${fim}`, new Date().toISOString());
    db.exec("COMMIT");
    return c.json({ id: Number(info.lastInsertRowid) }, 201);
  } catch {
    db.exec("ROLLBACK");
    return c.json({ erro: "Falha ao criar reserva" }, 500);
  }
});

app.put("/api/reservas/:id", async (c) => {
  const u = usuarioAtual(c);
  if (!u) return c.json({ erro: "Nao autenticado" }, 401);
  const id = Number(c.req.param("id"));
  const r = db.prepare("SELECT * FROM reservas WHERE id = ?").get(id);
  if (!r) return c.json({ erro: "Reserva nao encontrada" }, 404);
  if (r.usuario_id !== u.id && u.papel !== "admin") return c.json({ erro: "Sem permissao" }, 403);
  const corpo = await c.req.json();
  const salaId = Number(corpo.salaId ?? r.sala_id);
  const inicio = corpo.inicio ?? r.inicio;
  const fim = corpo.fim ?? r.fim;
  const erro = validar(inicio, fim);
  if (erro) return c.json({ erro }, 400);
  db.exec("BEGIN IMMEDIATE");
  try {
    const c2 = db.prepare(
      "SELECT id FROM reservas WHERE sala_id=? AND status='ativa' AND id<>? AND inicio < ? AND fim > ?",
    ).get(salaId, id, fim, inicio);
    if (c2) {
      db.exec("ROLLBACK");
      return c.json({ erro: "Conflito de horario para a sala" }, 409);
    }
    db.prepare("UPDATE reservas SET sala_id=?, inicio=?, fim=? WHERE id=?").run(salaId, inicio, fim, id);
    db.prepare("INSERT INTO historico (reserva_id,usuario_id,acao,detalhe,criado_em) VALUES (?,?,?,?,?)")
      .run(id, u.id, "edicao", `Reserva ${inicio} - ${fim}`, new Date().toISOString());
    db.exec("COMMIT");
    return c.json({ ok: true });
  } catch {
    db.exec("ROLLBACK");
    return c.json({ erro: "Falha ao editar" }, 500);
  }
});

app.delete("/api/reservas/:id", (c) => {
  const u = usuarioAtual(c);
  if (!u) return c.json({ erro: "Nao autenticado" }, 401);
  const id = Number(c.req.param("id"));
  const r = db.prepare("SELECT * FROM reservas WHERE id = ?").get(id);
  if (!r) return c.json({ erro: "Reserva nao encontrada" }, 404);
  if (r.usuario_id !== u.id && u.papel !== "admin") return c.json({ erro: "Sem permissao" }, 403);
  db.prepare("UPDATE reservas SET status='cancelada' WHERE id=?").run(id);
  db.prepare("INSERT INTO historico (reserva_id,usuario_id,acao,detalhe,criado_em) VALUES (?,?,?,?,?)")
    .run(id, u.id, "cancelamento", "Reserva cancelada", new Date().toISOString());
  return c.json({ ok: true });
});

app.get("/api/historico", (c) => {
  const u = usuarioAtual(c);
  if (!u) return c.json({ erro: "Nao autenticado" }, 401);
  const linhas = db.prepare(
    `SELECT h.id, h.acao, h.detalhe, h.criado_em AS criadoEm, us.nome AS usuario
     FROM historico h JOIN usuarios us ON us.id=h.usuario_id ORDER BY h.id DESC`,
  ).all();
  return c.json(linhas);
});

app.use("/*", serveStatic({ root: "./dist" }));
app.get("*", serveStatic({ path: "./dist/index.html" }));

const porta = Number(process.env.PORT || 3000);
serve({ fetch: app.fetch, port: porta, hostname: "0.0.0.0" }, (info) => {
  console.log(`ReservaFacil em http://0.0.0.0:${info.port}`);
});
