#!/usr/bin/env node
import { readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';

try {
  const { python } = JSON.parse(readFileSync(new URL('../runtime.json', import.meta.url), 'utf8'));
  const result = spawnSync(python, ['-I', '-m', 'dal.cli', ...process.argv.slice(2)], { stdio: 'inherit' });
  if (result.error) throw result.error;
  process.exitCode = result.status ?? 1;
} catch (error) {
  console.error(`DAL runtime is unavailable: ${error.message}\nRun the complete DAL installer again; see references/setup.md.`);
  process.exitCode = 1;
}
