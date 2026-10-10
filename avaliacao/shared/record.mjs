import fs from 'node:fs';
import path from 'node:path';

export function registrar(id, passou, motivo = '') {
  const dir = process.env.RESULTS_DIR;
  if (!dir) throw new Error('RESULTS_DIR nao definido');
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, `${id}.json`), JSON.stringify({ id, passou, motivo }, null, 2));
}
