import { randomUUID } from 'node:crypto';
import { lstat, mkdir, mkdtemp, readFile, readdir, rename, rm, writeFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';

export function skillDirectory(agent, project, home, global) {
  if (agent === 'claude-code') return join(global ? home : project, '.claude', 'skills', 'dal');
  if (agent === 'codex') return join(global ? home : project, global ? '.codex' : '.agents', 'skills', 'dal');
  throw new Error(`Unknown agent: ${agent}. Choose claude-code or codex.`);
}

async function skillFiles(source, relative = '') {
  const files = new Map();
  for (const entry of await readdir(join(source, relative), { withFileTypes: true })) {
    const name = join(relative, entry.name);
    if (entry.isDirectory()) for (const pair of await skillFiles(source, name)) files.set(...pair);
    else if (entry.isFile()) files.set(name, await readFile(join(source, name)));
  }
  return files;
}

export async function installSkill(source, target, python) {
  const files = await skillFiles(source);
  files.set('runtime.json', Buffer.from(JSON.stringify({ python }) + '\n'));
  const launcher = join(target, 'scripts', 'dal.mjs');
  const quote = value => process.platform === 'win32' ? `'${value.replaceAll("'", "''")}'` : `'${value.replaceAll("'", "'\\''")}'`;
  const command = `${process.platform === 'win32' ? '& ' : ''}${quote(process.execPath)} ${quote(launcher)}`;
  const text = files.get('SKILL.md').toString();
  files.set('SKILL.md', Buffer.from(text.replace('<!-- installed-runtime -->',
    `Use this exact launcher in place of \`dal\` in every command below:\n\n\`\`\`${process.platform === 'win32' ? 'powershell' : 'sh'}\n${command}\n\`\`\`\n\nIt uses absolute Node and Python paths and needs no PATH changes. Do not activate a shell environment.`)));

  let existing;
  try { existing = await lstat(target); } catch (error) { if (error.code !== 'ENOENT') throw error; }
  if (existing && !existing.isSymbolicLink()) {
    const matches = await Promise.all([...files].map(async ([name, content]) => {
      try { return content.equals(await readFile(join(target, name))); } catch { return false; }
    }));
    if (matches.every(Boolean)) return { target, command, unchanged: true };
  }

  await mkdir(dirname(target), { recursive: true });
  // Stage outside the skills directory: a partial installation must not be discoverable.
  const staged = await mkdtemp(join(dirname(dirname(target)), '.dal-install-'));
  let backup;
  try {
    for (const [name, content] of files) {
      await mkdir(dirname(join(staged, name)), { recursive: true });
      await writeFile(join(staged, name), content);
    }
    if (existing) {
      const backups = join(dirname(dirname(target)), 'dal-skill-backups');
      await mkdir(backups, { recursive: true });
      backup = join(backups, `dal-${randomUUID()}`);
      await rename(target, backup);
    }
    try { await rename(staged, target); }
    catch (error) {
      if (backup) await rename(backup, target);
      throw error;
    }
    return { target, command, backup, unchanged: false };
  } finally {
    await rm(staged, { recursive: true, force: true });
  }
}
