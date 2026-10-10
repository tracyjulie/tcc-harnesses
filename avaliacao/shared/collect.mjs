import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const cenario = process.argv[2];
const resultados = process.env.RESULTS_DIR;
if (!['site', 'jogo', 'app'].includes(cenario) || !resultados) {
  console.error('uso: RESULTS_DIR=<dir> node avaliacao/shared/collect.mjs <site|jogo|app>');
  process.exit(2);
}

const raiz = path.dirname(fileURLToPath(import.meta.url));
const pesos = JSON.parse(fs.readFileSync(path.join(raiz, '..', cenario, 'pesos.json'), 'utf8'));

const partesPorCriterio = {};
for (const arq of fs.readdirSync(resultados)) {
  if (!arq.endsWith('.json') || arq === 'test-results.json') continue;
  const r = JSON.parse(fs.readFileSync(path.join(resultados, arq), 'utf8'));
  const base = r.id.split('_')[0];
  (partesPorCriterio[base] ??= []).push(r);
}

const criterios = pesos.criterios.map((c) => {
  if (!c.verificavel) {
    return { id: c.id, descricao: c.descricao, peso: c.peso, verificavel: false, passou: null, motivo: c.motivo, partes: [] };
  }
  const partes = partesPorCriterio[c.id] ?? [];
  let passou = null;
  if (partes.some((p) => p.passou === 0)) passou = 0;
  else if (partes.length && partes.every((p) => p.passou === 1)) passou = 1;
  const motivo = partes.length === 0
    ? 'nao observado (teste nao executado)'
    : partes.filter((p) => p.passou !== 1).map((p) => `${p.id}: ${p.motivo}`).join(' | ') || 'ok';
  return { id: c.id, descricao: c.descricao, peso: c.peso, verificavel: true, passou, motivo, partes: partes.map((p) => p.id) };
});

fs.writeFileSync(
  path.join(resultados, 'test-results.json'),
  JSON.stringify({ cenario, gerado_em: new Date().toISOString(), criterios }, null, 2),
);
console.log(`test-results.json gravado em ${resultados} (${criterios.length} criterios)`);
