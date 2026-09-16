# Runtime setup

The skill contains agent instructions, not the Python runtime. DAL requires
Python 3.11 or newer. If installation is part of the user's request, use an
isolated environment in a software checkout; otherwise explain the missing
dependency before installing it.

```sh
git clone https://github.com/itamarwe/data-access-layer.git
cd data-access-layer
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
dal --help
```

On Windows, activate `.venv\Scripts\Activate.ps1` in PowerShell instead. Outside
an activated environment, use the environment's `dal` executable directly.

Do not replace an existing user's graph with the example. For an explicitly
requested demonstration, the checkout includes a synthetic shop:

```sh
dal --repository examples/shop build
dal --repository examples/shop search "orders by customer"
dal --repository examples/shop serve
```

Open `http://127.0.0.1:8765`; API documentation is at `/api/docs`. For a new empty
graph, use `dal --repository /path/to/context init`, add native resources, and
run `validate` followed by `build`.

BM25 works without embedding downloads. Optional hybrid retrieval requires
`python -m pip install -e '.[embeddings]'` and a build with
`--embedding-model BAAI/bge-small-en-v1.5`. This can download model weights;
embedding inference stays local. Do not upload private graph content to a hosted
model as a fallback.

The source checkout's `evals/README.md` documents synthetic retrieval benchmarks
and controlled SQL tests. These are not live-agent accuracy measurements.
