type Pos = { x: number; y: number };

const MAPA = [
  "############",
  "#........E.#",
  "#..P.......#",
  "#...#..#...#",
  "#...#K.#...#",
  "#...#..#...#",
  "#...####...#",
  "#..........#",
  "#........E.#",
  "#.........S#",
  "#.K......K.#",
  "############",
];

const LADO = MAPA.length;
const TAM = 40;
const TOTAL_CHAVES = 3;
let inicio: Pos = { x: 3, y: 2 };

const canvas = document.getElementById("game") as HTMLCanvasElement;
const ctx = canvas.getContext("2d")!;
const hud = {
  vidas: document.getElementById("hud-vidas")!,
  chaves: document.getElementById("hud-chaves")!,
  pontos: document.getElementById("hud-pontos")!,
  tempo: document.getElementById("hud-tempo")!,
  recorde: document.getElementById("hud-recorde")!,
};

let paredes: boolean[][] = [];
let saida: Pos = { x: 10, y: 9 };
let chaves: Pos[] = [];
let inimigos: Pos[] = [];
let jogador: Pos = { ...inicio };
let vidas = 3;
let coletadas = 0;
let pontos = 0;
let tempo = 0;
let pausado = false;
let estado: "jogando" | "vitoria" | "derrota" = "jogando";
let recorde = Number(localStorage.getItem("recorde") || "0");
let imortalAte = 0;

function carregarMapa(): void {
  paredes = [];
  chaves = [];
  inimigos = [];
  for (let y = 0; y < LADO; y += 1) {
    const linha: boolean[] = [];
    for (let x = 0; x < LADO; x += 1) {
      const c = MAPA[y][x];
      linha.push(c === "#");
      if (c === "K") chaves.push({ x, y });
      if (c === "E") inimigos.push({ x, y });
      if (c === "S") saida = { x, y };
      if (c === "P") inicio = { x, y };
    }
    paredes.push(linha);
  }
}

function ehParede(x: number, y: number): boolean {
  return x < 0 || y < 0 || x >= LADO || y >= LADO || paredes[y][x];
}

function reiniciar(): void {
  carregarMapa();
  jogador = { ...inicio };
  vidas = 3;
  coletadas = 0;
  pontos = 0;
  tempo = 0;
  pausado = false;
  estado = "jogando";
  imortalAte = 0;
  atualizarHud();
}

function mover(dx: number, dy: number): void {
  if (estado !== "jogando" || pausado) return;
  const nx = jogador.x + dx;
  const ny = jogador.y + dy;
  if (ehParede(nx, ny)) return;
  jogador = { x: nx, y: ny };
  const idx = chaves.findIndex((k) => k.x === nx && k.y === ny);
  if (idx >= 0) {
    chaves.splice(idx, 1);
    coletadas += 1;
    pontos += 100;
  }
  if (nx === saida.x && ny === saida.y && coletadas >= TOTAL_CHAVES) {
    estado = "vitoria";
    pontos += 500;
    salvarRecorde();
  }
  atualizarHud();
}

function moverInimigos(): void {
  if (estado !== "jogando" || pausado) return;
  for (const e of inimigos) {
    const dx = Math.sign(jogador.x - e.x);
    const dy = Math.sign(jogador.y - e.y);
    const tentativas: Pos[] = [
      { x: e.x + dx, y: e.y },
      { x: e.x, y: e.y + dy },
    ];
    for (const t of tentativas) {
      if (!ehParede(t.x, t.y)) {
        e.x = t.x;
        e.y = t.y;
        break;
      }
    }
    if (e.x === jogador.x && e.y === jogador.y && performance.now() > imortalAte) {
      vidas -= 1;
      imortalAte = performance.now() + 1500;
      jogador = { ...inicio };
      if (vidas <= 0) {
        vidas = 0;
        estado = "derrota";
        salvarRecorde();
      }
      atualizarHud();
    }
  }
}

function salvarRecorde(): void {
  if (pontos > recorde) {
    recorde = pontos;
    localStorage.setItem("recorde", String(recorde));
  }
  atualizarHud();
}

function atualizarHud(): void {
  hud.vidas.textContent = `Vidas: ${vidas}`;
  hud.chaves.textContent = `Chaves: ${coletadas}/${TOTAL_CHAVES}`;
  hud.pontos.textContent = `Pontos: ${pontos}`;
  hud.tempo.textContent = `Tempo: ${tempo}s`;
  hud.recorde.textContent = `Recorde: ${recorde}`;
}

function desenhar(): void {
  ctx.fillStyle = "#0b1118";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  for (let y = 0; y < LADO; y += 1) {
    for (let x = 0; x < LADO; x += 1) {
      if (paredes[y][x]) {
        ctx.fillStyle = "#2b3d50";
        ctx.fillRect(x * TAM, y * TAM, TAM - 1, TAM - 1);
      }
    }
  }
  ctx.fillStyle = coletadas >= TOTAL_CHAVES ? "#4ade80" : "#6b7280";
  ctx.fillRect(saida.x * TAM + 8, saida.y * TAM + 8, TAM - 16, TAM - 16);
  ctx.fillStyle = "#ffd166";
  for (const k of chaves) {
    ctx.beginPath();
    ctx.arc(k.x * TAM + TAM / 2, k.y * TAM + TAM / 2, TAM / 5, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.fillStyle = "#ff5a5a";
  for (const e of inimigos) {
    ctx.fillRect(e.x * TAM + 8, e.y * TAM + 8, TAM - 16, TAM - 16);
  }
  ctx.fillStyle = "#3fa7ff";
  ctx.beginPath();
  ctx.arc(jogador.x * TAM + TAM / 2, jogador.y * TAM + TAM / 2, TAM / 3, 0, Math.PI * 2);
  ctx.fill();
}

function tick(): void {
  if (estado === "jogando" && !pausado) {
    tempo += 1;
    moverInimigos();
    atualizarHud();
  }
}

window.addEventListener("keydown", (ev) => {
  const t = ev.key.toLowerCase();
  if (t === "arrowup" || t === "w") mover(0, -1);
  else if (t === "arrowdown" || t === "s") mover(0, 1);
  else if (t === "arrowleft" || t === "a") mover(-1, 0);
  else if (t === "arrowright" || t === "d") mover(1, 0);
  else if (t === "p") pausado = !pausado;
  else if (t === "r") reiniciar();
});

function publicarEstado(): void {
  (window as unknown as Record<string, unknown>).__labirinto = {
    jogador: { ...jogador },
    chaves: coletadas,
    totalChaves: TOTAL_CHAVES,
    vidas,
    pontos,
    tempo,
    estado,
    saidaLiberada: coletadas >= TOTAL_CHAVES,
    recorde,
    pausado,
    posicoesChaves: chaves.map((k) => ({ ...k })),
  };
}

function loop(): void {
  desenhar();
  publicarEstado();
  requestAnimationFrame(loop);
}

reiniciar();
setInterval(tick, 1200);
loop();
