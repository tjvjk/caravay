# Prototype SeamlessM4T on the reference Mac

Type: prototype
Status: resolved
Blocked by: 02

## Question

On the user's Apple-Silicon Mac and representative corpus, how useful are SeamlessM4T Medium's direct speech-to-English route and its ASR-then-text-translation route, and which supported runtime path is reliable enough for the MVP?

## Answer

On the reference MacBook Pro (M5 Max, 36 GB), the supported and reliable
runtime is PyTorch/Transformers on MPS with FP16, using the task-specific
`SeamlessM4TForSpeechToText` and `SeamlessM4TForTextToText` classes and
approximately ten-second chunks. All 30 chunks of the five-minute corpus ran
without a runtime failure. Peak RSS was 6.28 GiB. Direct speech-to-English ran
at 0.031 real-time factor; Armenian ASR followed by text translation ran at
0.081. CPU/FP32 is a functional fallback but was about 4.2x slower for direct
translation and 8.5x slower for the cascade in a ten-second control.

Direct speech-to-English is not useful enough for the MVP: it frequently loses
details and collapses into repeated generic phrases. The ASR-then-translation
route is more useful and debuggable and preserves substantially more of the
conversation, but still contains material recognition errors, hallucinations,
and repetitions. Neither route clears the MVP quality bar on this corpus;
task 04 should retain the cascaded route only as the stronger SeamlessM4T
Medium candidate when choosing whether to compare or reject the model route.

The executable spike is in [`prototypes/seamlessm4t/`](../../../prototypes/seamlessm4t/).
Full setup, measurements, examples, and raw outputs are in
[`seamlessm4t-prototype-results.md`](../seamlessm4t-prototype-results.md).
