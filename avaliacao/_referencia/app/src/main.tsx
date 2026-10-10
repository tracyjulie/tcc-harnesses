import { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";

type Usuario = { id: number; nome: string; email: string; papel: string };
type Sala = { id: number; nome: string; capacidade: number };
type Reserva = { id: number; salaId: number; sala: string; inicio: string; fim: string; usuarioId: number; usuario: string; status: string };
type Historico = { id: number; acao: string; detalhe: string; criadoEm: string; usuario: string };

async function api(caminho: string, opcoes: RequestInit = {}) {
  const resp = await fetch(caminho, {
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    ...opcoes,
  });
  const texto = await resp.text();
  const dados = texto ? JSON.parse(texto) : null;
  return { ok: resp.ok, status: resp.status, dados };
}

function App() {
  const [usuario, setUsuario] = useState<Usuario | null>(null);
  const [modo, setModo] = useState<"login" | "cadastro">("login");
  const [msg, setMsg] = useState<{ tipo: string; texto: string } | null>(null);
  const [salas, setSalas] = useState<Sala[]>([]);
  const [reservas, setReservas] = useState<Reserva[]>([]);
  const [historico, setHistorico] = useState<Historico[]>([]);
  const [verHistorico, setVerHistorico] = useState(false);
  const [editando, setEditando] = useState<number | null>(null);
  const [filtro, setFiltro] = useState({ sala: "", data: "", usuario: "" });

  async function carregar() {
    const s = await api("/api/salas");
    if (s.ok) setSalas(s.dados);
    const r = await api("/api/reservas");
    if (r.ok) setReservas(r.dados);
    const h = await api("/api/historico");
    if (h.ok) setHistorico(h.dados);
  }

  useEffect(() => {
    api("/api/auth/eu").then((r) => {
      if (r.ok) { setUsuario(r.dados); carregar(); }
    });
  }, []);

  async function registrar(ev: React.FormEvent<HTMLFormElement>) {
    ev.preventDefault();
    const f = new FormData(ev.currentTarget);
    const r = await api("/api/auth/registrar", {
      method: "POST",
      body: JSON.stringify({ nome: f.get("nome"), email: f.get("email"), senha: f.get("senha") }),
    });
    if (r.ok) { setUsuario(r.dados); setMsg(null); carregar(); }
    else setMsg({ tipo: "erro", texto: r.dados?.erro || "Falha no cadastro" });
  }

  async function entrar(ev: React.FormEvent<HTMLFormElement>) {
    ev.preventDefault();
    const f = new FormData(ev.currentTarget);
    const r = await api("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email: f.get("email"), senha: f.get("senha") }),
    });
    if (r.ok) { setUsuario(r.dados); setMsg(null); carregar(); }
    else setMsg({ tipo: "erro", texto: r.dados?.erro || "Credenciais invalidas" });
  }

  async function sair() {
    await api("/api/auth/logout", { method: "POST" });
    setUsuario(null);
    setReservas([]); setHistorico([]);
  }

  async function criarReserva(ev: React.FormEvent<HTMLFormElement>) {
    ev.preventDefault();
    const f = new FormData(ev.currentTarget);
    const r = await api("/api/reservas", {
      method: "POST",
      body: JSON.stringify({ salaId: Number(f.get("salaId")), inicio: f.get("inicio"), fim: f.get("fim") }),
    });
    if (r.ok) { setMsg({ tipo: "ok", texto: "Reserva criada" }); (ev.target as HTMLFormElement).reset(); carregar(); }
    else setMsg({ tipo: "erro", texto: r.dados?.erro || "Erro ao reservar" });
  }

  async function salvarEdicao(ev: React.FormEvent<HTMLFormElement>, id: number) {
    ev.preventDefault();
    const f = new FormData(ev.currentTarget);
    const r = await api(`/api/reservas/${id}`, {
      method: "PUT",
      body: JSON.stringify({ salaId: Number(f.get("salaId")), inicio: f.get("inicio"), fim: f.get("fim") }),
    });
    if (r.ok) { setMsg({ tipo: "ok", texto: "Reserva atualizada" }); setEditando(null); carregar(); }
    else setMsg({ tipo: "erro", texto: r.dados?.erro || "Erro ao editar" });
  }

  async function cancelar(id: number) {
    const r = await api(`/api/reservas/${id}`, { method: "DELETE" });
    if (r.ok) { setMsg({ tipo: "ok", texto: "Reserva cancelada" }); carregar(); }
    else setMsg({ tipo: "erro", texto: r.dados?.erro || "Erro ao cancelar" });
  }

  async function criarSala(ev: React.FormEvent<HTMLFormElement>) {
    ev.preventDefault();
    const f = new FormData(ev.currentTarget);
    const r = await api("/api/salas", {
      method: "POST",
      body: JSON.stringify({ nome: f.get("nome"), capacidade: Number(f.get("capacidade")) }),
    });
    if (r.ok) { (ev.target as HTMLFormElement).reset(); carregar(); }
    else setMsg({ tipo: "erro", texto: r.dados?.erro || "Erro ao criar sala" });
  }

  if (!usuario) {
    return (
      <main>
        <h1>ReservaFácil</h1>
        {msg && <p className={msg.tipo}>{msg.texto}</p>}
        {modo === "login" ? (
          <section>
            <h2>Entrar</h2>
            <form onSubmit={entrar}>
              <label>E-mail <input type="email" name="email" required /></label>
              <label>Senha <input type="password" name="senha" required /></label>
              <button type="submit">Entrar</button>
            </form>
            <button className="link" onClick={() => setModo("cadastro")}>Cadastrar</button>
          </section>
        ) : (
          <section>
            <h2>Cadastro</h2>
            <form onSubmit={registrar}>
              <label>Nome <input type="text" name="nome" required /></label>
              <label>E-mail <input type="email" name="email" required /></label>
              <label>Senha <input type="password" name="senha" required /></label>
              <button type="submit">Cadastrar</button>
            </form>
            <button className="link" onClick={() => setModo("login")}>Já tenho conta</button>
          </section>
        )}
      </main>
    );
  }

  const filtradas = reservas.filter((r) =>
    (!filtro.sala || String(r.salaId) === filtro.sala)
    && (!filtro.data || r.inicio.startsWith(filtro.data))
    && (!filtro.usuario || r.usuario.toLowerCase().includes(filtro.usuario.toLowerCase())));

  return (
    <main>
      <h1>ReservaFácil</h1>
      <div className="acoes">
        <span>Olá, {usuario.nome} ({usuario.papel})</span>
        <button onClick={sair}>Sair</button>
        <button onClick={() => { setVerHistorico((v) => !v); }}>Histórico</button>
      </div>
      {msg && <p className={msg.tipo}>{msg.texto}</p>}

      <section>
        <h2>Salas</h2>
        <ul>{salas.map((s) => <li key={s.id}>{s.nome} — capacidade {s.capacidade}</li>)}</ul>
        {usuario.papel === "admin" && (
          <form onSubmit={criarSala}>
            <label>Nome da sala <input type="text" name="nome" required /></label>
            <label>Capacidade <input type="number" name="capacidade" defaultValue={10} /></label>
            <button type="submit">Criar sala</button>
          </form>
        )}
      </section>

      {verHistorico && (
        <section>
          <h2>Histórico de alterações</h2>
          <ul>{historico.map((h) => <li key={h.id}>{h.acao} — {h.detalhe} ({h.usuario})</li>)}</ul>
        </section>
      )}

      <section>
        <h2>Nova reserva</h2>
        <form onSubmit={criarReserva}>
          <label>Sala
            <select name="salaId" required>
              <option value="">Selecione...</option>
              {salas.map((s) => <option key={s.id} value={s.id}>{s.nome}</option>)}
            </select>
          </label>
          <label>Início <input type="datetime-local" name="inicio" required /></label>
          <label>Fim <input type="datetime-local" name="fim" required /></label>
          <button type="submit">Reservar</button>
        </form>
      </section>

      <section>
        <h2>Reservas</h2>
        <div className="acoes">
          <label>Filtrar por sala
            <select value={filtro.sala} onChange={(e) => setFiltro({ ...filtro, sala: e.target.value })}>
              <option value="">Todas</option>
              {salas.map((s) => <option key={s.id} value={s.id}>{s.nome}</option>)}
            </select>
          </label>
          <label>Filtrar por data <input type="date" value={filtro.data} onChange={(e) => setFiltro({ ...filtro, data: e.target.value })} /></label>
          <label>Filtrar por usuário <input type="text" value={filtro.usuario} onChange={(e) => setFiltro({ ...filtro, usuario: e.target.value })} /></label>
        </div>
        <table>
          <thead><tr><th>Sala</th><th>Início</th><th>Fim</th><th>Usuário</th><th>Ações</th></tr></thead>
          <tbody>
            {filtradas.map((r) => (
              <tr key={r.id}>
                <td>{r.sala}</td><td>{r.inicio}</td><td>{r.fim}</td><td>{r.usuario}</td>
                <td className="acoes">
                  <button onClick={() => setEditando(editando === r.id ? null : r.id)}>Editar</button>
                  <button onClick={() => cancelar(r.id)}>Cancelar</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {editando !== null && (() => {
          const r = reservas.find((x) => x.id === editando);
          if (!r) return null;
          return (
            <form onSubmit={(e) => salvarEdicao(e, r.id)}>
              <h3>Editar reserva #{r.id}</h3>
              <label>Sala
                <select name="salaId" defaultValue={r.salaId}>
                  {salas.map((s) => <option key={s.id} value={s.id}>{s.nome}</option>)}
                </select>
              </label>
              <label>Início <input type="datetime-local" name="inicio" defaultValue={r.inicio} /></label>
              <label>Fim <input type="datetime-local" name="fim" defaultValue={r.fim} /></label>
              <button type="submit">Salvar</button>
            </form>
          );
        })()}
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
