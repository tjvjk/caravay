# SeamlessM4T Medium acceptance spike (THROWAWAY)

Run a short MPS smoke test from the repository root:

```sh
.venv/bin/python \
  prototypes/seamlessm4t/run.py \
  .scratch/caraway-offline-armenian-mvp/corpus/WncDNZDeWr0/WncDNZDeWr0_15m30s-20m30s.m4a \
  --duration 20 \
  --output .scratch/caraway-offline-armenian-mvp/results/seamlessm4t/smoke-mps.json
```

The first run downloads `facebook/hf-seamless-m4t-medium` (about 4.8 GB).
The disposable virtual environment lives at the repository root as `.venv`
and is ignored by Git. The executable prototype lives here, outside the issue
tracker. The script records direct speech-to-English, Armenian ASR followed by
text-to-English, per-stage timings, and peak process memory.
