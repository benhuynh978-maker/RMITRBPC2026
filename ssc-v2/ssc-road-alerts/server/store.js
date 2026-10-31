import { mkdir, readFile, open, rename, unlink } from 'node:fs/promises';
import { join } from 'node:path';
import { randomUUID } from 'node:crypto';
import { validateDataset } from './validation.js';
import { ApiError } from './errors.js';
const files = { cameras:'cameras.json', roads:'road-alerts.json' };
/** One writer process; serialize mutations and replace each JSON file atomically. */
export function createJsonStore(dataDir) {
  let tail = Promise.resolve();
  async function read(kind) {
    try {
      return validateDataset(JSON.parse(await readFile(join(dataDir, files[kind]), 'utf8')), kind)[kind];
    } catch (error) {
      if (error.code === 'ENOENT') return [];
      console.error(`[${files[kind]}] ${error.message}`);
      throw new ApiError(500, `Could not read ${files[kind]}. Fix the faulty data; the server will not overwrite this file.`);
    }
  }
  async function write(kind, rows) {
    validateDataset({[kind]:rows}, kind);
    await mkdir(dataDir, {recursive:true});
    const target = join(dataDir, files[kind]);
    const temp = `${target}.${randomUUID()}.tmp`;
    try {
      const handle = await open(temp, 'wx');
      try { await handle.writeFile(JSON.stringify({[kind]:rows}, null, 2) + '\n', 'utf8'); await handle.sync(); }
      finally { await handle.close(); }
      await rename(temp, target);
    } finally { await unlink(temp).catch(error => { if (error.code !== 'ENOENT') console.error(error.message); }); }
  }
  return {
    read: async kind => { await tail; return read(kind); },
    transaction(fn) {
      const operation = tail.then(() => fn({read,write}));
      tail = operation.catch(() => {});
      return operation;
    },
  };
}
