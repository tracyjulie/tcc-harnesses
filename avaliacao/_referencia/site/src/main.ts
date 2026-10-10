import "./style.css";

type Palestra = { titulo: string; trilha: "IA" | "Web" | "Segurança"; horario: string; palestrante: string };
type Inscricao = { nome: string; email: string; palestra: string };

const PALESTRAS: Palestra[] = [
  { titulo: "Fundamentos de IA", trilha: "IA", horario: "09:00", palestrante: "Ana Souza" },
  { titulo: "IA aplicada", trilha: "IA", horario: "10:00", palestrante: "Ana Souza" },
  { titulo: "Web moderna", trilha: "Web", horario: "11:00", palestrante: "Bruno Lima" },
  { titulo: "APIs e integração", trilha: "Web", horario: "13:00", palestrante: "Bruno Lima" },
  { titulo: "Segurança de aplicações", trilha: "Segurança", horario: "14:00", palestrante: "Carla Dias" },
  { titulo: "Criptografia na prática", trilha: "Segurança", horario: "15:00", palestrante: "Carla Dias" },
];

const PALESTRANTES = ["Ana Souza", "Bruno Lima", "Carla Dias"];

function montar(): void {
  const app = document.getElementById("app");
  if (!app) return;

  app.innerHTML = `
    <section id="programacao" aria-labelledby="t-programacao">
      <h2 id="t-programacao">Programação</h2>
      <div class="filtros" role="group" aria-label="Filtrar por trilha">
        <button type="button" data-trilha="Todas" aria-pressed="true">Todas</button>
        <button type="button" data-trilha="IA" aria-pressed="false">IA</button>
        <button type="button" data-trilha="Web" aria-pressed="false">Web</button>
        <button type="button" data-trilha="Segurança" aria-pressed="false">Segurança</button>
      </div>
      <ul class="palestras" id="lista-palestras"></ul>
    </section>
    <section id="palestrantes" aria-labelledby="t-palestrantes">
      <h2 id="t-palestrantes">Palestrantes</h2>
      <div class="palestrantes" id="lista-palestrantes"></div>
    </section>
    <section id="inscricao" aria-labelledby="t-inscricao">
      <h2 id="t-inscricao">Inscrição</h2>
      <form id="form-inscricao" novalidate>
        <label>Nome <input name="nome" type="text" /></label>
        <label>E-mail <input name="email" type="email" /></label>
        <label>Palestra
          <select name="palestra">
            <option value="">Selecione...</option>
            ${PALESTRAS.map((p) => `<option value="${p.titulo}">${p.titulo}</option>`).join("")}
          </select>
        </label>
        <button type="submit">Inscrever</button>
        <p class="erro" id="msg-erro" role="alert"></p>
      </form>
    </section>
  `;

  const listaPalestras = document.getElementById("lista-palestras")!;
  listaPalestras.innerHTML = PALESTRAS.map(
    (p) => `<li class="palestra" data-trilha="${p.trilha}">
      <strong>${p.titulo}</strong> — ${p.trilha} — ${p.horario} — ${p.palestrante}
    </li>`,
  ).join("");

  const divPalestrantes = document.getElementById("lista-palestrantes")!;
  divPalestrantes.innerHTML = PALESTRANTES.map(
    (n) => `<article class="palestrante"><h3>${n}</h3><p>Especialista convidado.</p></article>`,
  ).join("");

  document.querySelectorAll<HTMLButtonElement>(".filtros button").forEach((b) => {
    b.addEventListener("click", () => {
      const trilha = b.dataset.trilha!;
      document.querySelectorAll<HTMLButtonElement>(".filtros button").forEach((x) => {
        x.setAttribute("aria-pressed", String(x === b));
      });
      listaPalestras.querySelectorAll<HTMLLIElement>("li.palestra").forEach((li) => {
        const mostrar = trilha === "Todas" || li.dataset.trilha === trilha;
        li.style.display = mostrar ? "" : "none";
      });
    });
  });

  const form = document.getElementById("form-inscricao") as HTMLFormElement;
  const msgErro = document.getElementById("msg-erro")!;
  form.addEventListener("submit", (ev) => {
    ev.preventDefault();
    const nome = (form.elements.namedItem("nome") as HTMLInputElement).value.trim();
    const email = (form.elements.namedItem("email") as HTMLInputElement).value.trim();
    const palestra = (form.elements.namedItem("palestra") as HTMLSelectElement).value;
    msgErro.className = "erro";
    if (nome.length < 3) { msgErro.textContent = "Nome inválido: mínimo de 3 caracteres."; return; }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { msgErro.textContent = "E-mail inválido."; return; }
    if (!palestra) { msgErro.textContent = "Selecione uma palestra."; return; }

    const inscricoes = carregar();
    if (inscricoes.some((i) => i.email === email && i.palestra === palestra)) {
      msgErro.textContent = "Inscrição duplicada: você já está inscrito nesta palestra.";
      return;
    }
    inscricoes.push({ nome, email, palestra });
    localStorage.setItem("inscricoes", JSON.stringify(inscricoes));
    msgErro.className = "sucesso";
    msgErro.textContent = "Inscrição confirmada!";
    form.reset();
  });
}

function carregar(): Inscricao[] {
  try {
    const bruto = localStorage.getItem("inscricoes");
    const dados = bruto ? JSON.parse(bruto) : [];
    return Array.isArray(dados) ? dados : [];
  } catch {
    return [];
  }
}

montar();
