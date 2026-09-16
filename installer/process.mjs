import { spawnSync } from 'node:child_process';

export function run(command, args, options = {}) {
  const result = spawnSync(command, args, { stdio: 'inherit', ...options });
  if (result.error) throw new Error(`Cannot run ${command}: ${result.error.message}`);
  if (result.status !== 0) {
    const detail = result.stderr?.toString().trim();
    throw new Error(`${command} failed (${result.status ?? result.signal}).${detail ? `\n${detail}` : ''}`);
  }
  return result;
}
