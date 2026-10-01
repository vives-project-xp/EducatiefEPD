// Write a byte-for-byte MySQL dump; PowerShell's text redirection can change encoding.
import { spawn } from 'node:child_process';
import { createWriteStream } from 'node:fs';
import { mkdir, rm } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { pipeline } from 'node:stream/promises';

const stamp = new Date().toISOString().replaceAll(':', '-').replaceAll('.', '-');
const destination = resolve(process.argv[2] || join(import.meta.dirname, 'backups', `educatief_epd-${stamp}.sql`));
await mkdir(dirname(destination), { recursive: true });
const dump = spawn('docker', [
  'compose', 'exec', '-T', 'db', 'sh', '-c',
  'exec mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --single-transaction --routines --triggers --default-character-set=utf8mb4 "$MYSQL_DATABASE"',
], { cwd: import.meta.dirname, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
const closed = new Promise(resolve => dump.once('close', resolve));
let stderr = '';
dump.stderr.on('data', chunk => { stderr += chunk; });
const output = createWriteStream(destination, { flags: 'wx', mode: 0o600 });
let created = false;
output.once('open', () => { created = true; });
try {
  await pipeline(dump.stdout, output);
  const code = await closed;
  if (code !== 0) throw Error(`mysqldump failed (${code}): ${stderr.slice(-500)}`);
  console.log(`Backup written to ${destination}`);
} catch (error) {
  dump.kill();
  if (created) await rm(destination, { force: true });
  throw error;
}
