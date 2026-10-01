// Check that a live MySQL dump can be restored without touching the source schema.
import { spawn } from 'node:child_process';
import { createReadStream, createWriteStream } from 'node:fs';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { randomBytes } from 'node:crypto';
import { pipeline } from 'node:stream/promises';

const cwd = import.meta.dirname;
const temporary = await mkdtemp(join(tmpdir(), 'epd-restore-'));
const dump = join(temporary, 'database.sql');
const restoreSchema = `epd_restore_${randomBytes(6).toString('hex')}`;
let created = false;

function docker(command) {
  return spawn('docker', ['compose', 'exec', '-T', 'db', 'sh', '-c', command], {
    cwd, windowsHide: true, stdio: ['pipe', 'pipe', 'pipe'],
  });
}

async function completed(process) {
  const closed = new Promise(resolve => process.once('close', resolve));
  let stderr = '';
  process.stderr.on('data', chunk => { stderr += chunk; });
  const chunks = [];
  for await (const chunk of process.stdout) chunks.push(chunk);
  const code = await closed;
  if (code !== 0) throw Error(`Docker database command failed (${code}): ${stderr.slice(-500)}`);
  return Buffer.concat(chunks).toString('utf8').trim();
}

async function sql(query) {
  return completed(docker(`exec mysql -N -uroot -p"$MYSQL_ROOT_PASSWORD" -e '${query}'`));
}

async function tableCounts(schema) {
  return sql(`SELECT (SELECT COUNT(*) FROM ${schema}.dossier_case),
    (SELECT COUNT(*) FROM ${schema}.dossier_studentcase),
    (SELECT COUNT(*) FROM ${schema}.dossier_externalidentity);`);
}

try {
  const configured = await completed(docker('printf %s "$MYSQL_DATABASE"'));
  if (!/^[a-zA-Z0-9_]+$/.test(configured)) throw Error('Invalid configured database name');
  const before = await tableCounts(configured);

  const backup = docker('exec mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --single-transaction --routines --triggers --default-character-set=utf8mb4 "$MYSQL_DATABASE"');
  const backupClosed = new Promise(resolve => backup.once('close', resolve));
  let dumpError = '';
  backup.stderr.on('data', chunk => { dumpError += chunk; });
  await pipeline(backup.stdout, createWriteStream(dump));
  const dumpCode = await backupClosed;
  if (dumpCode !== 0) throw Error(`mysqldump failed (${dumpCode}): ${dumpError.slice(-500)}`);

  await sql(`CREATE DATABASE ${restoreSchema} CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;`);
  created = true;
  const restore = docker(`exec mysql -uroot -p"$MYSQL_ROOT_PASSWORD" ${restoreSchema}`);
  const restoreClosed = new Promise(resolve => restore.once('close', resolve));
  let restoreError = '';
  restore.stderr.on('data', chunk => { restoreError += chunk; });
  const drain = (async () => { for await (const _ of restore.stdout) { /* drain */ } })();
  await pipeline(createReadStream(dump), restore.stdin);
  await drain;
  const restoreCode = await restoreClosed;
  if (restoreCode !== 0) throw Error(`Restore failed (${restoreCode}): ${restoreError.slice(-500)}`);

  const after = await tableCounts(restoreSchema);
  if (before !== after) throw Error(`Restored record counts differ: ${before} vs ${after}`);
  console.log(`Backup restore verified: cases, student dossiers, identities = ${after.replaceAll('\t', ', ')}.`);
} finally {
  if (created && /^epd_restore_[0-9a-f]{12}$/.test(restoreSchema)) {
    await sql(`DROP DATABASE ${restoreSchema};`);
  }
  await rm(temporary, { recursive: true, force: true });
}
