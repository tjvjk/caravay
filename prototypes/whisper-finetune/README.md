# Armenian Whisper fine-tune spike (THROWAWAY)

From the repository root:

```sh
.venv/bin/python prototypes/whisper-finetune/run.py \
  .scratch/caraway-offline-armenian-mvp/corpus/WncDNZDeWr0/WncDNZDeWr0_15m30s-20m30s.m4a \
  --output .scratch/caraway-offline-armenian-mvp/results/whisper/armenian-medium-finetune.json
```

The script runs `ArthurYeghinyan/whisper-hy-am-asr-v2` through
Transformers/PyTorch MPS FP16 on the same fixed ten-second chunks used for the
SeamlessM4T comparison.
