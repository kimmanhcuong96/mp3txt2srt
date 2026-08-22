# me2listen Local Lesson Alignment

A fully local batch tool with two input modes:

```text
known English MP3/WAV + authoritative line-based `.en.txt` script
                         ↓
               WhisperX forced alignment
                         ↓
                    Standard SRT
```

When an `.en.txt` file is present, it controls the exact text, line boundaries, and
order. When it is absent, the application transcribes the MP3 locally and creates
one cue per punctuated English sentence. The source MP3 is never modified.

## Input and output

Put each MP3 beside an optional matching `.en.txt` script. For example,
`01_First Snow Fall.mp3` pairs with `01_First Snow Fall.en.txt`. The scanner is recursive, and every
subdirectory may contain any number of pairs:

```text
input/
├── unit-01/
│   ├── 001-greetings.mp3
│   ├── 001-greetings.en.txt
│   ├── 002-introductions.mp3
│   └── 002-introductions.en.txt
└── unit-02/
    ├── 001-daily-routine.mp3
    └── 001-daily-routine.en.txt
```

Every non-empty TXT line is exactly one subtitle cue. TXT must be UTF-8 and must
not contain timestamps, numbering, speaker labels, comments, or metadata.
Leading and trailing whitespace on each line is trimmed automatically; whitespace
inside the sentence is preserved for SRT output.

For MP3-only mode, place only the MP3 in `input/`. The tool uses local WhisperX
ASR (`large-v3-turbo`, English) followed by the existing English forced aligner.
It does not use an LLM or cloud API. The transcript is split into one cue per
punctuated sentence, treating a period after a capitalized title ("Dr.", "Mr.",
"Mrs.", "Ms.", "Prof.", "Rev.", "St.") as an abbreviation mark rather than a
sentence end — while still breaking correctly after "May 1st.", "500 ms.", and
a sentence-final letter such as "The answer is A." Wordless fragments
(punctuation the model emits for noise) are discarded first, and any sentence
under `transcription.min_sentence_words`
(default 5) is folded into the sentence after it — repeatedly, if still under
the minimum — or into the previous one if it's the last sentence with nothing to
merge forward into.

Successful output:

```text
output/
├── unit-01/
│   ├── 001-greetings.mp3  # byte-identical copy of the input
│   ├── 001-greetings.srt
│   ├── 002-introductions.mp3
│   └── 002-introductions.srt
└── unit-02/
    ├── 001-daily-routine.mp3
    └── 001-daily-routine.srt
```

Quality JSON is stored under `state/reports/`, logs under `logs/`, and resumable
job state in `state/jobs.sqlite`. None of those internal files enter an optional ZIP.

## Windows environment

Use the pinned Python 3.12.10 64-bit installer. WhisperX does not support Python
3.14 in the pinned release.

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

For the GTX 1660 Super, install the matching CUDA 12.8 PyTorch wheels first, then
the project. A current NVIDIA driver is required.

```powershell
python -m pip install torch==2.8.0 torchaudio==2.8.0 torchvision==0.23.0 `
  --index-url https://download.pytorch.org/whl/cu128
python -m pip install -e .
```

FFmpeg must also be installed and available on `PATH` because WhisperX uses it to
decode input audio:

```powershell
ffmpeg -version
```

The first script-based run may download the default English alignment model into
`state/models`. The first MP3-only run also downloads `large-v3-turbo`. After a
model is cached, set the relevant `model_cache_only: true` configuration value for
strictly offline runs.

## Run

```powershell
# Scan and process all pairs sequentially
python -m me2listen_alignment

# Resume: completed outputs are skipped; queued/interrupted/failed jobs are processed
python -m me2listen_alignment --resume

# One or more paths relative to input/ (without extension)
python -m me2listen_alignment --lesson unit-01/001-greetings

# Override the input root
python -m me2listen_alignment --input .\my-lessons

# CPU fallback
python -m me2listen_alignment --device cpu

# Process and package completed pairs only
python -m me2listen_alignment --package
python -m me2listen_alignment --package-only
```

`--resume` is explicit for readability; normal runs use the same durable state and
also skip completed jobs. A changed input file resets its job to queued. Missing
output assets also reset a completed job.

Exit codes: `0` success, `1` one or more lesson failures, `2` setup/configuration
error, `130` interrupted.

## Alignment and quality behavior

For script mode, the engine creates one known-transcript segment spanning the real
audio duration and calls `whisperx.align()` directly. For MP3-only mode, it first
transcribes English with `large-v3-turbo`, releases that ASR model from GPU memory,
then aligns Whisper's timestamped segments with the same English
`WAV2VEC2_ASR_BASE_960H` aligner. Timestamp interpolation is forced to `ignore`.

WhisperX's batched transcription path does not apply faster-whisper's own
no-speech/low-confidence filtering, so a window of background music, singing, or
unclear audio can otherwise decode into a single confident-sounding boilerplate
phrase (e.g. "We'll see you next time.") repeated for every chunk instead of
failing loudly. Any transcribed segment whose `avg_logprob` falls below
`transcription.min_avg_logprob` (default `-1.0`, matching faster-whisper's own
`logprob_threshold`) is dropped; if nothing confident remains, the lesson fails
with a clear error instead of producing a wrong SRT that still passes quality
checks.

`transcription.device` (the ASR step, ctranslate2-based) defaults to `cpu`,
independently of `alignment.device` (the forced-alignment step, PyTorch-based),
which defaults to `cuda`. Script-mode lessons never construct the ASR engine at
all, so this only affects MP3-only lessons. The split default exists because
ctranslate2 CUDA inference can silently return wrong, input-independent output
on GPUs without Tensor Cores (verified on a GTX 1660 SUPER: the same model
produced identical "transcribed" text for real audio, silence, and random
noise), while the same model on CPU transcribes correctly and the PyTorch
alignment step already runs correctly on that same GPU. If your GPU handles
ctranslate2 correctly, set `transcription.device: cuda` for speed; otherwise
leave it on `cpu`.

Aligned tokens are matched in order to tokens from each authoritative script line.
Each cue starts at its earliest matched word and ends at its latest matched word.
A boundary-refinement pass then detects real low-energy gaps around adjacent cues:
the previous cue ends near the beginning of the measured silence and the next cue
starts near its end. This prevents either cue from containing the neighboring word.
If no reliable silence is found within the configured search radius, the original
WhisperX word timing is retained rather than guessed.
If WhisperX stretches the first or last aligned word across a long silence because
the audio contains an unlisted spoken title, intro, or outro, that external speech
is excluded at the measured silence boundary. Script text remains the only target.

Boundary refinement is configurable under `alignment`:

- `boundary_silence_threshold_db`: energy threshold used to recognize silence.
- `boundary_silence_minimum`: shortest accepted silence interval in seconds.
- `boundary_search_radius`: maximum distance from the WhisperX boundary.
- `boundary_speech_padding`: small safety margin retained beside speech.
- `boundary_embedded_silence_minimum`: long silence used to reject unlisted intro/outro speech.

A line with no aligned words, non-monotonic/overlapping timing, or coverage below the
configured failure threshold produces `FAIL` and no SRT. Long lines are retained
unchanged and reported as warnings.

Defaults are in [`config/default.yaml`](config/default.yaml): English, batch size 1,
99% PASS coverage, 95% minimum acceptable coverage. `alignment.device` defaults to
`cuda`. The `transcription` section controls MP3-only mode (`large-v3-turbo`,
`int8`, English, batch size 1) and defaults `transcription.device` to `cpu`
independently of `alignment.device` — see the device note above. To fit a 6 GB
GPU, the ASR model is released before the alignment model loads.

## Tests

The unit tests do not download a model or require a GPU:

```powershell
python -m unittest discover -s tests -v
```
