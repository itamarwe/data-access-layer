import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { cp, lstat, mkdir, mkdtemp, readFile, rm, symlink, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { parseOptions } from '../cli.mjs';
import { assetFor, runtimeFingerprint, verifyDownload } from '../runtime.mjs';
import { installSkill, skillDirectory } from '../skill.mjs';

const root = fileURLToPath(new URL('../../', import.meta.url));
async function temporary(t) {
  const directory = await mkdtemp(join(tmpdir(), 'dal-installer-test-'));
  t.after(() => rm(directory, { recursive: true, force: true }));
  return directory;
}

test('parse installer options without accepting misspelled or ignored arguments', () => {
  assert.equal(parseOptions([]).agent, 'claude-code');
  assert.equal(parseOptions(['install', '--agent', 'codex', '--global']).global, true);
  assert.equal(parseOptions(['--embeddings']).embeddings, true);
  for (const args of [['--agent', 'unknown'], ['publish'], ['--globall']]) assert.throws(() => parseOptions(args));
});

test('agent destinations distinguish project and user scope', () => {
  assert.equal(skillDirectory('claude-code', 'project', 'user', false), join('project', '.claude', 'skills', 'dal'));
  assert.equal(skillDirectory('claude-code', 'project', 'user', true), join('user', '.claude', 'skills', 'dal'));
  assert.equal(skillDirectory('codex', 'project', 'user', false), join('project', '.agents', 'skills', 'dal'));
  assert.equal(skillDirectory('codex', 'project', 'user', true), join('user', '.codex', 'skills', 'dal'));
  assert.throws(() => skillDirectory('unknown', '', '', false));
});

test('only supported verified artifacts are accepted', () => {
  for (const platform of ['darwin', 'linux', 'win32']) for (const arch of ['x64', 'arm64']) {
    assert.equal(assetFor(platform, arch)[1].length, 64);
  }
  assert.throws(() => assetFor('linux', 'ia32'), /Unsupported/);
  const bytes = Buffer.from('verified artifact');
  verifyDownload(bytes, createHash('sha256').update(bytes).digest('hex'));
  assert.throws(() => verifyDownload(Buffer.from('changed'), '0'.repeat(64)), /checksum mismatch/);
});

test('installation records its interpreter and does not change a matching skill', async t => {
  const directory = await temporary(t);
  const target = join(directory, 'space and quotes \' $', 'skills', 'dal');
  const python = join(directory, 'private python');
  const first = await installSkill(join(root, 'skills/dal'), target, python);
  const second = await installSkill(join(root, 'skills/dal'), target, python);
  assert.equal(first.unchanged, false);
  assert.equal(second.unchanged, true);
  assert.equal(JSON.parse(await readFile(join(target, 'runtime.json'), 'utf8')).python, python);
  assert.ok((await readFile(join(target, 'SKILL.md'), 'utf8')).includes(first.command));
  assert.ok(await readFile(join(target, 'references/setup.md'), 'utf8'));
});

test('changed skill is preserved outside skill discovery before replacement', async t => {
  const directory = await temporary(t);
  const target = join(directory, '.claude/skills/dal');
  await mkdir(target, { recursive: true });
  await writeFile(join(target, 'SKILL.md'), 'my existing skill');
  const installed = await installSkill(join(root, 'skills/dal'), target, '/python');
  assert.equal(await readFile(join(installed.backup, 'SKILL.md'), 'utf8'), 'my existing skill');
  assert.equal(dirname(dirname(installed.backup)), join(directory, '.claude'));
});

test('legacy skills-installer symlink is replaced without modifying its source', async t => {
  const directory = await temporary(t);
  const source = join(directory, 'old-skill');
  const target = join(directory, '.claude/skills/dal');
  await mkdir(source);
  await writeFile(join(source, 'SKILL.md'), 'original');
  await mkdir(dirname(target), { recursive: true });
  await symlink(source, target, process.platform === 'win32' ? 'junction' : 'dir');
  const installed = await installSkill(join(root, 'skills/dal'), target, '/python');
  assert.equal(await readFile(join(source, 'SKILL.md'), 'utf8'), 'original');
  assert.equal((await lstat(installed.backup)).isSymbolicLink(), true);
  assert.equal((await lstat(target)).isSymbolicLink(), false);
});

test('runtime identity covers Python sources, UI assets, dependencies and extras', async t => {
  const directory = await temporary(t);
  await mkdir(join(directory, 'dal/api/static'), { recursive: true });
  await writeFile(join(directory, 'pyproject.toml'), '[project]');
  await writeFile(join(directory, 'dal/a.py'), 'one');
  const first = await runtimeFingerprint(directory, false);
  assert.notEqual(first, await runtimeFingerprint(directory, true));
  await writeFile(join(directory, 'dal/api/static/index.html'), 'ui');
  assert.notEqual(first, await runtimeFingerprint(directory, false));
  const second = await runtimeFingerprint(directory, false);
  await writeFile(join(directory, 'dal/a.py'), 'two');
  assert.notEqual(second, await runtimeFingerprint(directory, false));
});

test('launcher forwards arguments and nonzero exit codes without requiring Python on PATH', async t => {
  const directory = await temporary(t);
  const target = join(directory, 'skill');
  await cp(join(root, 'skills/dal'), target, { recursive: true });
  await writeFile(join(target, 'runtime.json'), JSON.stringify({ python: process.execPath }));
  // Node rejects Python's -I argument, proving the configured executable was used.
  const result = spawnSync(process.execPath, [join(target, 'scripts/dal.mjs'), '--help'], { encoding: 'utf8', env: { ...process.env, PATH: '' } });
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /bad option: -I/);
});

test('missing runtime fails with recovery instructions', async t => {
  const directory = await temporary(t);
  await cp(join(root, 'skills/dal'), directory, { recursive: true });
  const result = spawnSync(process.execPath, [join(directory, 'scripts/dal.mjs'), '--help'], { encoding: 'utf8' });
  assert.equal(result.status, 1);
  assert.match(result.stderr, /complete DAL installer again/);
});
