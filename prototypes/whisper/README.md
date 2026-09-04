# MLX Whisper Armenian STT spike (THROWAWAY)

From the repository root:

```sh
.venv/bin/python prototypes/whisper/run.py \
  .scratch/caraway-offline-armenian-mvp/corpus/WncDNZDeWr0/WncDNZDeWr0_15m30s-20m30s.m4a \
  --output .scratch/caraway-offline-armenian-mvp/results/whisper/large-v3-turbo.json
```

The default is the unquantized `mlx-community/whisper-large-v3-turbo`
checkpoint. The script forces Armenian transcription, retains word/segment
timestamps, and records wall time including model loading and peak RSS.

Use `--no-condition-on-previous-text` when an erroneous window causes long
cross-window repetitions. Use `--no-word-timestamps` for a faster control run.
