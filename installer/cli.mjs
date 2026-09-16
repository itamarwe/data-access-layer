#!/usr/bin/env node
import { homedir } from 'node:os';
import { realpathSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseArgs } from 'node:util';
import { ensureRuntime } from './runtime.mjs';
import { installSkill, skillDirectory } from './skill.mjs';

export function parseOptions(args) {
  const { values, positionals } = parseArgs({ args, allowPositionals: true, options: {
    agent: { type: 'string', default: 'claude-code' },
    global: { type: 'boolean', default: false },
    embeddings: { type: 'boolean', default: false },
    help: { type: 'boolean', short: 'h' },
  } });
  if (positionals.length > 1 || (positionals.length && positionals[0] !== 'install')) {
    throw new Error('Usage: dal-context-graph install [--agent claude-code|codex] [--global] [--embeddings]');
  }
  if (!['claude-code', 'codex'].includes(values.agent)) throw new Error('Choose --agent claude-code or --agent codex.');
  return values;
}

export async function main(args = process.argv.slice(2)) {
  const options = parseOptions(args);
  if (options.help) {
    console.log('Usage: dal-context-graph install [--agent claude-code|codex] [--global] [--embeddings]\nInstalls the skill, private Python 3.12, and DAL. Default: Claude Code in the current project.\nRequires Node.js 20+, internet, and tar. No Python setup, shell edits, or credentials needed.\nDAL_HOME overrides the private runtime location (~/.local/share/dal).');
    return;
  }
  const root = dirname(dirname(fileURLToPath(import.meta.url)));
  const target = skillDirectory(options.agent, process.cwd(), homedir(), options.global);
  const home = resolve(process.env.DAL_HOME || join(homedir(), '.local', 'share', 'dal'));
  console.log(`Installing DAL for ${options.agent}\nSkill: ${target}\nPrivate runtime: ${home}`);
  const python = await ensureRuntime(root, home, options.embeddings);
  const result = await installSkill(join(root, 'skills', 'dal'), target, python);
  if (result.backup) console.log(`Previous skill preserved at: ${result.backup}`);
  console.log(`${result.unchanged ? 'Already installed' : 'Installed'} and verified.\nCLI: ${result.command}\nUse ${options.agent === 'claude-code' ? '/dal' : '$dal'} and provide your context repository path.`);
}

if (process.argv[1] && realpathSync(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch(error => { console.error(`DAL installation failed: ${error.message}`); process.exitCode = 1; });
}
