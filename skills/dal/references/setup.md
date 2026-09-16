# Complete installation

Run from the agent's project directory (Node.js 20+, internet, and `tar` required):

```sh
npx github:itamarwe/data-access-layer install --agent claude-code
```

Use `--agent codex` for Codex, or add `--global` for all projects. The installer
downloads checksum-verified uv, installs private Python 3.12 and DAL dependencies,
tests the CLI, and only then installs the skill. It does not require system Python,
change shell profiles, configure warehouse credentials, or create a context graph.

The installed SKILL.md gives the exact `node /absolute/path/scripts/dal.mjs`
launcher. Use it instead of `dal` in examples. It does not depend on shell
activation or DAL being on PATH. Keep `runtime.json` and the referenced private
runtime local to this machine; do not commit or copy them to another machine.
Run the installer on each machine instead.

Re-running reuses a healthy matching runtime. An existing changed skill is backed
up outside the discoverable skills directory before replacement, including an
older instructions-only installation. The installer prints its backup location.
Runtime files default to `~/.local/share/dal`; `DAL_HOME` can select another path.
Re-run the installer to repair missing runtime files. Keep old runtime directories
while other installed skills still point to them.

BM25 works immediately. Add `--embeddings` to install optional embedding libraries;
then build the graph with `--embedding-model BAAI/bge-small-en-v1.5` to acquire
weights. This can download model weights; inference remains local. Private graph
content is never uploaded by the installer.

If only `npx skills add ...` was used, it copied instructions without running this
installer. Run the complete command above to finish setup.

For contributors, the source checkout still supports Python 3.11+ with an editable
installation (`python -m pip install -e '.[dev]'`). See the repository README for
the synthetic shop demonstration and `evals/README.md` for benchmarks.
