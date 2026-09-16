// Networked end-to-end test of the actual npm tarball; all installs are temporary.
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { cp, mkdir, mkdtemp, readFile, readdir, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { run } from '../process.mjs';

const root = fileURLToPath(new URL('../../', import.meta.url));
const directory = await mkdtemp(join(tmpdir(), 'dal-npx-smoke-'));
console.log(`Isolated installer test: ${directory}`);
const npm = process.env.npm_execpath;
assert.ok(npm, 'Run this test through npm run test:install.');
const env = { ...process.env, DAL_HOME: join(directory, 'private runtime'), npm_config_cache: join(directory, 'npm-cache') };
try {
  run(process.execPath, [npm, 'pack', '--quiet', '--pack-destination', directory], { cwd: root });
  const tarball = (await readdir(directory)).find(name => name.endsWith('.tgz'));
  const project = join(directory, 'project with spaces');
  await mkdir(project);
  const installArgs = [npm, 'exec', '--yes', '--package', join(directory, tarball), '--', 'dal-context-graph', 'install'];
  run(process.execPath, installArgs, { cwd: project, env });
  const skill = join(project, '.claude/skills/dal');
  const runtimeBefore = await readFile(join(skill, 'runtime.json'), 'utf8');
  const launcher = join(skill, 'scripts/dal.mjs');
  const graph = join(project, 'context');
  await cp(join(root, 'examples/shop/semantic'), join(graph, 'semantic'), { recursive: true });
  const invoke = args => run(process.execPath, [launcher, ...args], { cwd: project, env: { ...env, PATH: '' }, stdio: 'pipe', encoding: 'utf8' }).stdout;
  invoke(['--help']);
  invoke(['--repository', graph, 'validate']);
  invoke(['--repository', graph, 'build']);
  const result = invoke(['--repository', graph, 'search', 'orders by customer']);
  assert.match(result, /orders-by-customer/);
  const invalid = spawnSync(process.execPath, [launcher, 'invalid-command'], { env, stdio: 'pipe' });
  assert.equal(invalid.status, 2);
  const { python } = JSON.parse(runtimeBefore);
  run(python, ['-I', '-c', 'from importlib.resources import files; assert files("dal.api").joinpath("static/index.html").is_file()']);
  run(python, ['-I', '-c', `
import sys
from pathlib import Path
from dal.api.app import create_app
from dal.api.config import ServerConfig
from dal.api.services import APIServices
from dal.mcp import create_mcp
root = Path(sys.argv[1])
config = ServerConfig(repository_root=root, bundle=root / ".dal" / "query")
services = APIServices.create(config)
assert create_app(config, services=services).openapi()["info"]["title"] == "DAL context API"
assert create_mcp(services.catalog, services.health) is not None
`, graph]);
  run(process.execPath, installArgs, { cwd: project, env });
  assert.equal(await readFile(join(skill, 'runtime.json'), 'utf8'), runtimeBefore);
  run(process.execPath, [...installArgs, '--agent', 'codex'], { cwd: project, env });
  assert.equal(await readFile(join(project, '.agents/skills/dal/runtime.json'), 'utf8'), runtimeBefore);
  run(process.execPath, [...installArgs, '--embeddings'], { cwd: project, env });
  const upgraded = JSON.parse(await readFile(join(skill, 'runtime.json'), 'utf8'));
  assert.notEqual(upgraded.python, python);
  run(upgraded.python, ['-I', '-c', 'import fastembed, numpy, usearch']);
  assert.equal(await readFile(join(project, '.agents/skills/dal/runtime.json'), 'utf8'), runtimeBefore);
  console.log('PASS: packed npx install, private Python, no-PATH CLI, graph build/search, UI/API/MCP, repeated install, Codex, and optional embeddings.');
} finally {
  await rm(directory, { recursive: true, force: true });
}
