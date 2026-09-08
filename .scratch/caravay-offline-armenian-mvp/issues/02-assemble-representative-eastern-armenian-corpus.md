# Assemble a representative Eastern Armenian corpus

Type: task
Status: resolved

## Question

What 10–20 user-relevant Eastern Armenian audio fragments and corresponding evaluation prompts will represent clean speech, room noise, conversational pace, names, and numbers well enough to judge the MVP model on the user's actual use case?

## Answer

For the first acceptance prototype, use the five-minute excerpt from
[`WncDNZDeWr0`](https://www.youtube.com/watch?v=WncDNZDeWr0), covering
`15:30–20:30`. It contains conversational Eastern Armenian and is accompanied
by YouTube's automatic Armenian transcript and automatic English translation.

Corpus artifacts:

- [`WncDNZDeWr0_15m30s-20m30s.m4a`](../corpus/WncDNZDeWr0/WncDNZDeWr0_15m30s-20m30s.m4a)
- [`WncDNZDeWr0_15m30s-20m30s.hy.srt`](../corpus/WncDNZDeWr0/WncDNZDeWr0_15m30s-20m30s.hy.srt)
- [`WncDNZDeWr0_15m30s-20m30s.en.srt`](../corpus/WncDNZDeWr0/WncDNZDeWr0_15m30s-20m30s.en.srt)

The corpus is intentionally smaller than the originally proposed 10–20
fragments. It is sufficient to exercise the end-to-end prototype and expose
obvious quality or runtime failures. The automatic subtitles are comparison
aids, not ground-truth references; human judgment remains required. Expand the
corpus only if this first run leaves the model-route decision ambiguous.
