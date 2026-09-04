Я бы сделал это как маленький Unix-friendly CLI `mt`, где **ASR и перевод — сменные backend'ы**, а модели можно брать прямо с Hugging Face.

```text
audio/stdin
   ↓
ASR backend
   ↓
text stream
   ↓
MT backend
   ↓
stdout / JSONL / subtitles
```

Основные команды выглядели бы так:

```bash
mt transcribe --model openai/whisper-small
mt translate de:ru --model facebook/nllb-200-distilled-600M
mt listen de:ru
```

И всё должно нормально работать через pipe:

```bash
mt transcribe --lang de |
mt translate de:ru
```

или:

```bash
cat transcript.txt |
mt translate en:ru
```

Для live-встреч:

```bash
mt listen de:ru
```

внутри делает:

```text
system audio
→ VAD
→ Whisper
→ partial/final text
→ translation model
→ terminal
```

Конфиг, например `~/.config/mt/config.toml`:

```toml
[asr]
engine = "whisper"
model = "openai/whisper-small"
device = "auto"

[translation]
engine = "hf"
model = "facebook/nllb-200-distilled-600M"
source = "de"
target = "ru"
device = "auto"

[audio]
device = "BlackHole 2ch"

[output]
format = "pretty"
show_original = true
```

CLI-аргументы просто override'ят конфиг:

```bash
mt listen de:ru --model some-user/some-translation-model
```

Я бы поддержал три формата вывода:

```bash
mt listen de:ru
```

человеческий:

```text
DE  Wir verschieben den Termin auf Dienstag.
RU  Мы переносим встречу на вторник.
```

Unix-режим:

```bash
mt listen de:ru --output text
```

только перевод в `stdout`.

И машинный:

```bash
mt listen de:ru --output jsonl
```

```json
{"ts":12.4,"source":"de","text":"Guten Morgen","target":"ru","translation":"Доброе утро","final":true}
```

Архитектурно core должен вообще не знать конкретных моделей:

```python
class ASR:
    def transcribe(...): ...

class Translator:
    def translate(...): ...
```

Поэтому позже можно безболезненно добавлять:

```text
ASR:
  whisper.cpp
  faster-whisper
  mlx-whisper

MT:
  Hugging Face Transformers
  CTranslate2
  Argos
  локальная LLM
```

Идея в итоге такая: **`mt` — это не одна модель, а Unix-обвязка над speech→text→translation pipeline.** Модели пользователь выбирает сам, конфиг хранит дефолты, а всё можно комбинировать через stdin/stdout.


Да, именно. Я бы вообще сделал **не live-переводчик, а универсальный pipeline**, где live audio — всего лишь один из источников.

```text
INPUT → ASR? → MT? → OUTPUT
```

Каждый кубик опционален.

Например, обычный перевод текста — без ASR:

```bash
echo "Guten Morgen" | mt translate de:ru
```

```text
text → MT → stdout
```

Перевод файла:

```bash
mt translate de:ru transcript.txt
```

Транскрибация без перевода:

```bash
mt transcribe meeting.mp3
```

```text
audio file → ASR → stdout
```

Транскрибация + перевод файла:

```bash
mt transcribe meeting.mp3 --lang de |
mt translate de:ru
```

```text
meeting.mp3
    ↓
   ASR
    ↓
   MT
    ↓
 stdout
```

А live — просто другой input:

```bash
mt listen --lang de |
mt translate de:ru
```

```text
system audio
     ↓
    ASR
     ↓
     MT
     ↓
   stdout
```

И можно дать удобный shortcut:

```bash
mt listen de:ru
```

который эквивалентен предыдущему pipeline.

В идеале даже модели должны быть отдельными заменяемыми компонентами:

```bash
mt translate de:ru \
  --model facebook/nllb-200-distilled-600M
```

или через конфиг:

```toml
[asr]
model = "openai/whisper-small"

[mt]
model = "facebook/nllb-200-distilled-600M"
```

Тогда философия проекта получается очень чистая:

```text
                 ┌─ text ───────────────┐
                 │                      ↓
mic/system ──→ ASR ───────────────────→ MT ──→ stdout
                 ↑                      ↑
audio file ──────┘                      │
                                        │
text/file ──────────────────────────────┘
```

То есть **live вообще не является core-фичей**. Core — это composable CLI для локальных open-source ASR/MT-моделей, а `listen` — один из адаптеров ввода.

Я бы именно вокруг этой идеи и проектировал API/CLI — тогда потом туда естественно добавятся `TTS`, subtitles `.srt`, batch processing и другие кубики, не ломая архитектуру.

Отличие я бы сформулировал так:

```text
Не "AI meeting translator"

а

"ffmpeg for local AI language models"
```

То есть одна утилита:

```bash
mt transcribe audio.mp3
mt translate de:ru
mt listen
```

и композиция:

```bash
mt listen --lang de |
mt translate de:ru
```

или:

```bash
mt transcribe meeting.mp3 |
mt translate de:ru |
tee meeting.ru.txt
```

или вообще:

```bash
cat german.txt |
mt translate de:ru \
  --model Helsinki-NLP/opus-mt-de-ru
```

При этом модели — **не захардкожены**:

```bash
mt models pull Helsinki-NLP/opus-mt-de-ru

mt translate de:ru \
  --model Helsinki-NLP/opus-mt-de-ru
```

А ASR аналогично:

```bash
mt transcribe meeting.wav \
  --model openai/whisper-large-v3
```

И затем можно добавить ещё один кубик:

```text
        ┌──── ASR ────┐
        │             │
input ──┼──── MT ─────┼──→ output
        │             │
        └──── TTS ────┘
```

Например:

```bash
mt transcribe meeting.mp3 |
mt translate de:ru |
mt speak --voice ru
```

Вот **такой generic, model-agnostic, Hugging-Face-friendly, stdin/stdout-first CLI** среди найденных проектов я не вижу. Существующие проекты обычно начинаются с конкретного use case — meeting translator, live stream translator, dubbing, web UI — а у нас use case получается следствием композиции примитивов.

И это, на мой взгляд, намного интереснее как open-source проект: **`curl`, `ffmpeg`, `jq`, но для ASR/MT/TTS**.


