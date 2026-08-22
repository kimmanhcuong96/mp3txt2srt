# me2listen — Local Lesson Alignment Pipeline
# Case A: MP3 + Script → Standard SRT
# Case B: MP3-only → Standard SRT (local ASR fallback, Section 3B)

## 1. OBJECTIVE

Build a fully local, free Python application that converts:

Case A — a `.en.txt` script is supplied:

MP3 + TXT Script
    ↓
WhisperX Forced Alignment
    ↓
Word-level timestamps
    ↓
Script-line mapping
    ↓
Standard SRT
    ↓
Validation / Quality Report

Case B — no `.en.txt` exists for that lesson (see Section 3B):

MP3 only
    ↓
Local English ASR (confidence-gated)
    ↓
Punctuated sentence lines
    ↓
WhisperX Forced Alignment  (same engine as Case A)
    ↓
Word-level timestamps
    ↓
Script-line mapping
    ↓
Standard SRT
    ↓
Validation / Quality Report

The application is responsible for converting an existing audio file — with or
without a corresponding script — into a precisely timed Standard SRT file. When
a script is supplied it remains the absolute source of truth (Section 2). When
it is absent, local ASR generates the sentence lines instead, and every rule
below that refers to "the script" applies to that ASR-generated text (Section 3B).

The application must be completely independent from me2listen.

It must NOT require:

- me2listen database
- me2listen backend
- me2listen API
- authentication
- OpenAI API
- Gemini API
- cloud transcription
- cloud alignment
- paid services
- YouTube
- yt-dlp

The application does NOT download or modify source audio.

Final output contract:

lesson-name.mp3
lesson-name.srt


## 2. CORE DESIGN PRINCIPLE

The script is the ABSOLUTE SOURCE OF TRUTH for:

- exact lesson content
- sentence boundaries
- sentence order

WhisperX is responsible ONLY for determining timing.

The pipeline must NOT automatically:

- split sentences
- merge sentences
- rewrite sentences
- paraphrase sentences
- reorder sentences
- correct grammar
- replace the supplied script with ASR output

Conceptually:

Script
  = Content + Sentence Boundaries

WhisperX
  = Timing

Pipeline
  = Alignment + Mapping + Validation + SRT Generation


## 3. INPUT CONTRACT

Each lesson consists of:

lesson-name.mp3
lesson-name.en.txt

Example:

001-greetings.mp3
001-greetings.en.txt

The script file must be UTF-8 plain text.


## 3B. MP3-ONLY MODE (CASE B)

When a lesson's `.en.txt` is absent, the pipeline falls back to local ASR
instead of requiring a script:

lesson-name.mp3   (no lesson-name.en.txt)

Flow:

1. Transcribe the MP3 locally with faster-whisper (`large-v3-turbo`,
   English-only; no other language is auto-detected).
2. Drop any transcribed segment whose `avg_logprob` is below
   `transcription.min_avg_logprob` (default `-1.0`, matching faster-whisper's
   own `logprob_threshold`). WhisperX's batched transcription path does not
   apply faster-whisper's own no-speech/low-confidence filtering, so without
   this gate a low-confidence window (background music, an unclear voice,
   near-silence) can decode into one confident-sounding boilerplate phrase
   repeated for every chunk instead of failing. If nothing confident remains,
   the lesson fails with a clear error — it must never produce a
   plausible-looking but wrong SRT.
3. Split the surviving transcript into one sentence per punctuation mark
   (`.`, `!`, `?`). First discard any fragment containing no words at all
   (punctuation the model emits for noise or hesitation) so its text can never
   reach a cue — this happens before the abbreviation step below, otherwise
   such a fragment could ride into a sentence attached to a preceding
   abbreviation. Then suppress the break where the period is an abbreviation
   mark rather than a full stop: a capitalized title from `ABBREVIATIONS`
   ("Dr.", "Mr.", "Mrs.", "Ms.", "Prof.", "Rev.", "St."), which essentially
   never ends an English sentence. Three constraints keep that test from
   over-firing, each covering a verified failure: a word boundary, so the
   ordinal suffix of "1st." / "21st." is not read as "St."; required
   capitalization, so the unit "500 ms." is not read as "Ms."; and no
   single-letter/initials rule, since protecting "J. K. Rowling" would cost
   every sentence ending in "I." or a spoken letter ("The answer is A."),
   which this lesson material is far likelier to contain. The list stays small
   for the same reason: wrongly joining two sentences is a milder error than
   wrongly cutting one in half, but that asymmetry only justifies entries that
   are unambiguous, so words that genuinely do end sentences ("etc.", "Inc.",
   "Jr.") and titles absent from this material are left out.
   Any remaining sentence under `transcription.min_sentence_words` (default 5)
   words is folded into the sentence right after it — repeatedly, if the merged
   result is still under the minimum — since a short fragment ("Yes.", "OK.")
   is rarely a usable standalone subtitle cue; a trailing short fragment with
   no next sentence is folded into the previous one instead. What remains
   becomes the same script-line structure Case A builds from the `.en.txt`
   file — from this point on, Sections 9-18 (normalization, word-level
   alignment, line-to-cue mapping, SRT format, validation, quality report)
   apply identically to Case A.
4. Force-align the ASR segments with the SAME WhisperX aligner used in Case A
   (Section 7). ASR only supplies text; WhisperX still supplies all timing —
   Section 2's "Script = Content, WhisperX = Timing" principle is unchanged,
   with ASR output standing in for the script as the content source.

The ASR step and the alignment step are deliberately separate engines/model
loads so that a problem in one cannot corrupt the other (see Section 20B).

Case B never runs for a lesson that has a `.en.txt` file. Case A's script
remains the absolute source of truth whenever one exists; local ASR only fills
the gap when no script was supplied at all.


## 4. SCRIPT FORMAT

### 4.1 One line = one sentence / utterance

Every non-empty line represents exactly ONE sentence or natural utterance.

Example:

Hello, how are you today?
I'm doing very well, thank you.
It's nice to meet you.

Blank lines between sentences are NOT required.

The canonical format is:

ONE SENTENCE PER LINE.

Leading and trailing whitespace on each non-empty line is automatically trimmed
before validation and SRT generation. Lines containing only whitespace are ignored.

### 4.2 Sentence boundaries are authoritative

If the script contains:

Hello, how are you today?
I'm doing very well, thank you.

the output MUST contain exactly two subtitle cues.

The pipeline MUST NOT automatically split or merge these lines.

### 4.3 No timestamps

Do NOT use:

[00:01.500] Hello, how are you?

### 4.4 No subtitle numbering

Do NOT use:

1. Hello, how are you?
2. I'm fine.

### 4.5 No speaker labels

Speaker labels are NOT supported in v1.

Do NOT use:

John: Hello, how are you?
Mary: I'm fine.

### 4.6 No metadata

The TXT file must NOT contain:

- lesson title
- lesson ID
- slug
- timestamps
- subtitle numbering
- speaker metadata
- comments
- me2listen metadata
- configuration

The filename identifies the lesson.


## 5. SCRIPT MUST MATCH THE AUDIO

The script must contain the actual words spoken in the MP3.

The script is NOT a corrected or rewritten version of the speech.

Correct:

Audio:
I wanna go there.

Script:
I wanna go there.

Incorrect:

Audio:
I wanna go there.

Script:
I want to go there.

Another example:

Audio:
I'm gonna go to work.

Script:
I'm gonna go to work.

The pipeline MUST NOT use an LLM to rewrite the script.

The supplied script is the transcript to be aligned.

An audio file may contain a spoken title, intro, or outro that is intentionally not
part of the lesson script. When such external speech is separated from the target
content by a reliable long silence, exclude it from the first/last SRT cue. Do not
add the external speech to SRT and do not rewrite the supplied script.


## 6. AUDIO REQUIREMENTS

Input audio is MP3.

The audio should preferably contain approximately:

0.5–1.0 seconds of leading silence

before the first spoken sentence.

This prevents the learner from hearing speech immediately after pressing Play.

IMPORTANT:

The alignment application MUST NOT automatically insert silence.

It receives the MP3 as an existing source asset.

The source audio should be prepared correctly before entering this pipeline.

The application may detect and report leading silence as a quality metric, but must NOT modify the MP3.


## 7. ALIGNMENT ENGINE

Use WhisperX as the primary local forced-alignment engine.

WhisperX must be used for:

MP3 + known transcript
        ↓
word-level timestamps

Do NOT use an LLM for timing.

Do NOT use ASR output to replace the supplied script.

The supplied script remains the source of truth.


## 8. ALIGNMENT FLOW

Required processing flow:

MP3
 +
TXT
 ↓
Script validation
 ↓
Internal alignment normalization
 ↓
WhisperX forced alignment
 ↓
Word-level timestamps
 ↓
Map aligned words to original script lines
 ↓
Calculate line start/end
 ↓
Generate Standard SRT
 ↓
Validate
 ↓
Quality report


## 9. SCRIPT NORMALIZATION

The pipeline MAY create an internal normalized representation for alignment.

Possible normalization:

- Unicode normalization
- whitespace normalization
- apostrophe/quote normalization
- harmless punctuation normalization
- transformations required by the alignment engine

However:

The ORIGINAL script text must always be preserved for SRT output.

Maintain separate values:

original_script_line
alignment_script_line

The normalized alignment text MUST NEVER replace the original text in SRT.


## 10. WORD-LEVEL ALIGNMENT

WhisperX should produce word-level timestamps.

Example:

Hello       1.02 → 1.31
how         1.32 → 1.55
are         1.56 → 1.72
you         1.73 → 1.91
today       1.92 → 2.34

For:

Hello, how are you today?

derive:

start = first aligned word.start
end   = last aligned word.end

Therefore:

Hello, how are you today?
1.02 → 2.34

Do NOT estimate timing from:

- character count
- word count
- average speaking rate
- proportional segment division
- arbitrary fixed durations


## 11. SCRIPT LINE → SRT CUE

There MUST be a strict 1:1 mapping:

script line 1 → SRT cue 1
script line 2 → SRT cue 2
script line 3 → SRT cue 3

Example:

TXT:

Hello, how are you today?
I'm doing very well, thank you.
It's nice to meet you.

SRT:

1
00:00:01,020 --> 00:00:02,340
Hello, how are you today?

2
00:00:03,100 --> 00:00:04,620
I'm doing very well, thank you.

3
00:00:05,400 --> 00:00:06,800
It's nice to meet you.

The pipeline MUST NOT automatically split or merge these lines.


## 12. LONG SENTENCES

If a script line is too long for recommended subtitle readability:

DO NOT automatically split it.

Instead report:

WARNING: sentence exceeds recommended subtitle length

The original sentence remains intact.

The user decides whether to modify the script/audio.


## 13. TIMING RULES

For every script line:

start = earliest aligned word start
end   = latest aligned word end

When adjacent WhisperX cue boundaries touch or bleed into neighboring speech, the
pipeline may refine the boundary using a measured low-energy/silence interval in the
source audio. The previous cue ends near the start of that silence and the next cue
starts near its end. If no reliable silence exists nearby, retain the original
WhisperX word timing rather than inventing a boundary.

Required:

start < end

Timing must come from actual aligned words.

Do NOT:

- estimate timing
- interpolate timing unnecessarily
- use LLM-generated timing
- divide a larger segment proportionally
- create artificial durations


## 14. SRT FORMAT

The output MUST be Standard SRT.

Example:

1
00:00:01,020 --> 00:00:02,340
Hello, how are you today?

2
00:00:03,100 --> 00:00:04,620
I'm doing very well, thank you.

Each entry contains only:

- sequence number
- timestamp
- original script text

Do NOT add:

- lesson title
- lesson ID
- slug
- custom metadata
- me2listen metadata
- comments
- custom headers


## 15. SRT TEXT MUST MATCH ORIGINAL SCRIPT

SRT text must come directly from the original TXT line.

TXT:

I'm doing very well, thank you.

SRT:

I'm doing very well, thank you.

Do NOT transform it into:

I am doing very well, thank you.

or:

I'm doing very well thank you

Alignment normalization must never modify the final subtitle text.


## 16. NO AUTOMATIC SENTENCE SEGMENTATION

There is NO AI sentence-segmentation step.

Do NOT implement:

Word timestamps
    ↓
AI decides sentence boundaries

Instead:

TXT lines
    ↓
fixed sentence boundaries
    ↓
word timestamps mapped to each line

The user/script author controls subtitle boundaries.


## 17. VALIDATION

Before a lesson is marked COMPLETED, validate:

### Files

- MP3 exists
- TXT exists
- SRT exists
- basename relationship is correct

### Script

- UTF-8
- non-empty
- at least one non-empty line
- valid line structure
- no timestamps
- no numbering
- no unsupported metadata
- no speaker labels

### Alignment

- every script line is mapped
- every line has aligned words
- start < end
- timestamps are monotonic
- no impossible timestamps
- alignment coverage is measurable

### SRT

- valid SRT syntax
- valid timestamps
- continuous sequence numbers
- no empty text
- no invalid overlaps
- no subtitle beyond audio duration
- number of cues equals number of script lines


## 18. ALIGNMENT QUALITY REPORT

Generate a quality report for every lesson.

Example:

Total script lines: 20
Successfully aligned: 20
Alignment coverage: 99.2%
Timing issues: 0
Suspicious lines: 1

Each lesson receives:

PASS
WARNING
FAIL

Example:

PASS
Alignment coverage: 99.5%
All lines aligned
No timing errors

WARNING
Alignment coverage: 97.2%
1 sentence has unusually low alignment confidence

FAIL
Alignment coverage: 83.4%
2 sentences could not be aligned

Thresholds must be configurable.

If alignment is unreliable, do NOT invent timing.

Mark the lesson for human review.


## 19. HARDWARE TARGET

Target machine:

CPU:
Intel Core i5 9th generation

GPU:
NVIDIA GTX 1660 Super 6 GB VRAM

RAM:
16 GB

Expected workload:

~100 lessons per batch
~2 minutes per lesson
~200 minutes total

No parallel processing is required.

Sequential processing is preferred.

Priorities:

1. stability
2. correctness
3. resume capability
4. low memory usage
5. predictable behavior
6. throughput


## 20. GPU PROCESSING

Initial target:

device: CUDA
batch_size: 1

Load the alignment model once and reuse it:

START
 ↓
load model
 ↓
process lesson 1
 ↓
process lesson 2
 ↓
process lesson 3
 ...
 ↓
process lesson 100
 ↓
release model

Do NOT:

- load all audio into RAM
- process 100 files concurrently
- reload the model for every lesson


## 20B. ASR DEVICE ISOLATION (CASE B)

`transcription.device` (the local ASR step, ctranslate2-based, Section 3B) and
`alignment.device` (the forced-alignment step, PyTorch-based, Section 20) are
independent settings and default independently:

alignment.device: cuda
transcription.device: cpu

This split exists because, on the target GTX 1660 Super (Section 19 — a Turing
GPU with no Tensor Cores), ctranslate2 CUDA inference was found to silently
return wrong, input-independent output: the same model produced the identical
"transcribed" text for real audio, for pure silence, and for random noise. The
same model on CPU transcribed that audio correctly, and the PyTorch alignment
step already runs correctly on that same GPU (proven by every Case A lesson
processed so far). If a target GPU is confirmed to run ctranslate2 correctly,
`transcription.device` may be set to `cuda` for speed; the default stays `cpu`
for correctness. Case A never constructs the ASR engine at all, so it is
unaffected by either setting.


## 21. MODEL CONFIGURATION

Model and compute settings must be configurable.

Initial configuration should target:

GTX 1660 Super 6 GB

Example:

device: cuda

alignment:
  batch_size: 1

If memory pressure occurs, support a lower-memory configuration where supported.

Do not aggressively optimize before benchmarking real lesson data.


## 22. PYTHON ENVIRONMENT

Use a dedicated virtual environment.

Do NOT rely on global Python packages.

Pin compatible versions of:

- Python
- PyTorch
- WhisperX
- faster-whisper / CTranslate2
- alignment dependencies

Verify actual compatibility before locking versions.

Do NOT assume Python 3.14 compatibility.


## 23. INPUT DIRECTORY

Recommended structure:

input/
├── unit-01/
│   ├── 001-greetings.mp3
│   ├── 001-greetings.en.txt
│   ├── 002-introductions.mp3
│   └── 002-introductions.en.txt
│
└── unit-02/
    ├── 001-daily-routine.mp3
    └── 001-daily-routine.en.txt

Match the MP3 basename with the part before `.en.txt`:

001-greetings.mp3
001-greetings.en.txt

Each MP3 and TXT pair must be located in the same directory.

The input directory may contain any number of nested subdirectories.
Each subdirectory may contain multiple MP3/TXT pairs.


## 24. OUTPUT DIRECTORY

Example:

output/
├── unit-01/
│   ├── 001-greetings.mp3
│   ├── 001-greetings.srt
│   ├── 002-introductions.mp3
│   └── 002-introductions.srt
│
└── unit-02/
    ├── 001-daily-routine.mp3
    └── 001-daily-routine.srt

The output directory must preserve the relative subdirectory structure from input.

The MP3 is the original input audio.

The tool must NOT modify or replace it.

Only the SRT is generated.


## 25. BATCH PROCESSING

Process lessons sequentially:

Queue
 ↓
Lesson 1
 ↓
Lesson 2
 ↓
Lesson 3
 ↓
...

Example progress:

Total:       100
Completed:    37
Processing:    1
Failed:        2
Remaining:    60

A single failed lesson must not terminate the entire batch.


## 26. RESUME / RETRY

The pipeline must support resume.

Example:

100 lessons
63 completed
2 failed
35 remaining

After restart:

Resume
 ↓
skip completed
 ↓
process remaining

Do not unnecessarily reprocess successful lessons.

Each job has:

queued
processing
completed
failed

Failed jobs must contain a useful error message.


## 27. LOCAL JOB STATE

Use lightweight local state such as SQLite.

No database server is required.

Suggested fields:

job_id
lesson_name
audio_path
script_path
srt_path
status
attempt_count
error_message
created_at
updated_at

This state is internal to the preparation tool and unrelated to the me2listen production database.


## 28. LOGGING

Maintain local logs.

Log:

- lesson name
- processing start/end
- model configuration
- alignment result
- alignment coverage
- warnings
- errors
- retry count
- processing duration

Logs must never alter the SRT format.


## 29. OPTIONAL BATCH PACKAGING

After validation passes, optionally create:

me2listen-batch-001.zip

Containing only:

001-greetings.mp3
001-greetings.srt
002-introductions.mp3
002-introductions.srt
...

Do NOT include:

- TXT files
- temporary files
- WhisperX intermediate files
- logs
- SQLite state
- internal metadata

unless explicitly requested.


## 30. RECOMMENDED PROJECT ARCHITECTURE

Suggested structure:

me2listen-alignment/
├── pyproject.toml
├── README.md
├── config/
│   └── default.yaml
│
├── src/
│   └── me2listen_alignment/
│       ├── cli.py
│       ├── config.py
│       ├── models.py
│       ├── batch.py
│       ├── jobs.py
│       │
│       ├── script/
│       │   ├── parser.py
│       │   ├── normalizer.py
│       │   └── validator.py
│       │
│       ├── alignment/
│       │   ├── whisperx_engine.py
│       │   └── mapper.py
│       │
│       ├── subtitle/
│       │   ├── srt_writer.py
│       │   └── validator.py
│       │
│       └── quality/
│           └── analyzer.py
│
├── input/
├── output/
├── logs/
└── state/
    └── jobs.sqlite

The exact structure may be adjusted during implementation, but responsibilities should remain separated.


## 31. EXPLICIT NON-GOALS

Do NOT implement:

- YouTube downloading
- yt-dlp
- FFmpeg-based YouTube extraction
- MP3 conversion
- MP3 modification
- LLM integration
- cloud transcription
- cloud alignment
- automatic sentence splitting or merging of a SUPPLIED script (Case A)
- automatic script rewriting
- automatic grammar correction
- speaker diarization
- me2listen API integration
- me2listen database integration
- authentication

Local ASR (Case B, Section 3B) is a narrow, explicit exception to the original
"no ASR" rule: it exists ONLY to produce sentence lines when a lesson has no
`.en.txt` at all, runs fully offline with no cloud/LLM involvement, and never
overrides a script that IS supplied — Case A's rules in Section 2 are unchanged.


## 32. SUCCESS CRITERIA

The implementation is successful when it reliably processes:

MP3 + TXT (Case A), or MP3 alone (Case B, Section 3B)

and produces:

Standard SRT

with these guarantees:

1. Every script line (Case A: from `.en.txt`; Case B: from confidence-gated ASR)
   becomes exactly one SRT cue.
2. SRT text exactly matches the source script line — the original TXT line in
   Case A, the punctuated ASR sentence in Case B.
3. Timing is derived from WhisperX word-level forced alignment in both cases.
4. No sentence is automatically split or merged once it is a script line.
5. Invalid/unreliable alignment OR unreliable ASR is detected instead of
   silently producing bad data (Section 3B, item 2).
6. Output passes Standard SRT validation.
7. Audio and SRT have identical basenames.
8. Batch processing is sequential and memory-safe.
9. Failed jobs can be retried.
10. Completed jobs can be resumed/skipped.
11. The entire pipeline runs locally without paid APIs or cloud services,
    including the Case B ASR step.
12. The output can be imported into me2listen without preparation-tool-specific metadata.


## 33. MOST IMPORTANT IMPLEMENTATION RULE

Do NOT build a generic speech-to-subtitle system.

Build a:

"Known English Script → Accurately Timed SRT"

system, where the "known script" is either the supplied `.en.txt` (Case A) or a
confidence-gated local ASR transcript that stands in for it when no `.en.txt`
exists (Case B, Section 3B). Once that script text exists — supplied or
transcribed — it is treated exactly the same way from Section 9 onward: WhisperX
never re-decides what was said, only when it was said.

The script controls:

- exact content
- exact sentence boundaries
- sentence order

WhisperX controls:

- word-level timing

The pipeline controls:

- script validation
- alignment
- word-to-line mapping
- SRT generation
- SRT validation
- quality reporting
- batch processing
- retry/resume
- optional packaging

Final contract:

Input:
lesson-name.mp3
lesson-name.en.txt

Output:
lesson-name.mp3
lesson-name.srt

The MP3 is preserved as the original source asset.
The SRT is the only generated lesson asset.
