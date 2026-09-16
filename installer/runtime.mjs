import { createHash } from 'node:crypto';
import { chmod, mkdir, mkdtemp, readFile, readdir, rename, rm, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { run } from './process.mjs';

const uv = JSON.parse(await readFile(new URL('./uv.json', import.meta.url), 'utf8'));

export function assetFor(platform = process.platform, arch = process.arch) {
  const asset = uv.assets[`${platform}-${arch}`];
  if (!asset) throw new Error(`Unsupported platform: ${platform}/${arch}. Use the Python source installation instead.`);
  return asset;
}

export function verifyDownload(bytes, expected) {
  if (createHash('sha256').update(bytes).digest('hex') !== expected) {
    throw new Error('uv download checksum mismatch; nothing from the archive was executed.');
  }
}

async function bootstrapUv(home) {
  const [name, checksum] = assetFor();
  const scratch = await mkdtemp(join(home, 'uv-'));
  try {
    const url = `https://github.com/astral-sh/uv/releases/download/${uv.version}/${name}`;
    console.log(`Downloading verified uv ${uv.version}…`);
    const response = await fetch(url, { signal: AbortSignal.timeout(120_000) });
    if (!response.ok) throw new Error(`uv download failed: HTTP ${response.status}`);
    const bytes = Buffer.from(await response.arrayBuffer());
    verifyDownload(bytes, checksum);
    const archive = join(scratch, name);
    await writeFile(archive, bytes);
    run('tar', ['-xf', archive, '-C', scratch]);
    const executable = process.platform === 'win32'
      ? join(scratch, 'uv.exe') : join(scratch, name.replace('.tar.gz', ''), 'uv');
    await chmod(executable, 0o755);
    return { executable, scratch };
  } catch (error) {
    await rm(scratch, { recursive: true, force: true });
    throw error;
  }
}

export async function runtimeFingerprint(root, embeddings) {
  const hash = createHash('sha256').update(JSON.stringify({ embeddings, python: '3.12', uv: uv.version }));
  async function visit(relative) {
    for (const entry of (await readdir(join(root, relative), { withFileTypes: true })).sort((a, b) => a.name.localeCompare(b.name))) {
      const name = `${relative}/${entry.name}`;
      if (entry.isDirectory() && entry.name !== '__pycache__') await visit(name);
      else if (entry.isFile() && (name.endsWith('.py') || name.startsWith('dal/api/static/'))) {
        hash.update(name).update(await readFile(join(root, name)));
      }
    }
  }
  hash.update(await readFile(join(root, 'pyproject.toml')));
  await visit('dal');
  return hash.digest('hex');
}

export async function ensureRuntime(root, home, embeddings = false) {
  const fingerprint = await runtimeFingerprint(root, embeddings);
  await mkdir(home, { recursive: true });
  const record = join(home, `${fingerprint}.json`);
  try {
    const cached = JSON.parse(await readFile(record, 'utf8'));
    run(cached.python, ['-I', '-m', 'dal.cli', '--help'], { stdio: 'pipe' });
    console.log('Using the verified installed DAL runtime.');
    return cached.python;
  } catch (error) {
    if (error.code !== 'ENOENT') console.log('The cached runtime is unavailable; preparing a fresh installation.');
  }
  const { executable, scratch } = await bootstrapUv(home);
  const runtime = await mkdtemp(join(home, 'runtime-'));
  const python = process.platform === 'win32' ? join(runtime, 'Scripts', 'python.exe') : join(runtime, 'bin', 'python');
  const env = {
    ...process.env,
    UV_PYTHON_INSTALL_DIR: join(home, 'python'),
    UV_CACHE_DIR: join(home, 'cache'),
    UV_PYTHON_BIN_DIR: join(home, 'python-bin'),
    UV_NO_PROGRESS: '1',
  };
  try {
    console.log('Installing private Python 3.12 and DAL dependencies…');
    run(executable, ['venv', '--no-config', '--managed-python', '--python', '3.12', runtime], { env });
    const requirement = `dal-context-graph${embeddings ? '[embeddings]' : ''} @ ${pathToFileURL(root).href}`;
    run(executable, ['pip', 'install', '--no-config', '--python', python, requirement], { env });
    run(python, ['-I', '-m', 'dal.cli', '--help'], { stdio: 'pipe' });
    const temporaryRecord = join(runtime, 'installed.json');
    await writeFile(temporaryRecord, JSON.stringify({ python, fingerprint }) + '\n');
    await rename(temporaryRecord, record);
    return python;
  } catch (error) {
    await rm(runtime, { recursive: true, force: true });
    throw error;
  } finally {
    await rm(scratch, { recursive: true, force: true });
  }
}
