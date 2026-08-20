# me2listen Local Lesson Alignment

A fully local batch tool for one specific job:

```text
known English MP3 + authoritative line-based TXT script
                         ↓
               WhisperX forced alignment
                         ↓
                    Standard SRT
```

The script controls the exact text, line boundaries, and order. WhisperX supplies
word timestamps only. The application never transcribes, rewrites, splits, merges,
or modifies the source MP3.

## Input and output

Put each MP3 beside its matching `.en.txt` script. For example,
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
decode MP3 files:

```powershell
ffmpeg -version
```

The first run may download the default English alignment model into `state/models`.
After it is cached, set `model_cache_only: true` for strictly offline runs.

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

The engine creates one known-transcript segment spanning the real audio duration and
calls `whisperx.align()` directly—there is no ASR transcription step. WhisperX's
timestamp interpolation is forced to `ignore`. Untimed words therefore reduce
coverage instead of receiving invented timestamps.

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

Defaults are in [`config/default.yaml`](config/default.yaml): CUDA, English, batch
size 1, 99% PASS coverage, 95% minimum acceptable coverage. The alignment model is
loaded once and reused across the sequential batch.

## Tests

The unit tests do not download a model or require a GPU:

```powershell
python -m unittest discover -s tests -v
```
