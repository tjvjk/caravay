# SeamlessM4T Medium acceptance spike (THROWAWAY)

Run a short MPS smoke test from the repository root:

```sh
.venv/bin/python \
  prototypes/seamlessm4t/run.py \
  .scratch/caravay-offline-armenian-mvp/corpus/WncDNZDeWr0/WncDNZDeWr0_15m30s-20m30s.m4a \
  --duration 20 \
  --output .scratch/caravay-offline-armenian-mvp/results/seamlessm4t/smoke-mps.json
```

The first run downloads `facebook/hf-seamless-m4t-medium` (about 4.8 GB).
The disposable virtual environment lives at the repository root as `.venv`
and is ignored by Git. The executable prototype lives here, outside the issue
tracker. The script records direct speech-to-English, Armenian ASR followed by
text-to-English, per-stage timings, and peak process memory.

Pass `--model v2-large` to test `facebook/seamless-m4t-v2-large` using the
corresponding task-specific v2 classes. Its two safetensor shards total about
9.2 GB.
