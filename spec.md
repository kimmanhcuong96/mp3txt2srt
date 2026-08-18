# me2listen — Local Lesson Alignment Pipeline
# Case A: MP3 + Script → Standard SRT

## 1. OBJECTIVE

Build a fully local, free Python application that converts:

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

The application is responsible ONLY for converting an existing audio file and its corresponding script into a precisely timed Standard SRT file.

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
lesson-name.txt

Example:

001-greetings.mp3
001-greetings.txt

The script file must be UTF-8 plain text.


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
│   ├── 001-greetings.txt
│   ├── 002-introductions.mp3
│   └── 002-introductions.txt
│
└── unit-02/
    ├── 001-daily-routine.mp3
    └── 001-daily-routine.txt

Match files by basename:

001-greetings.mp3
001-greetings.txt

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
- ASR
- MP3 → transcript
- automatic transcript generation
- LLM integration
- cloud transcription
- cloud alignment
- automatic sentence splitting
- automatic sentence merging
- automatic script rewriting
- automatic grammar correction
- speaker diarization
- me2listen API integration
- me2listen database integration
- authentication


## 32. SUCCESS CRITERIA

The implementation is successful when it reliably processes:

MP3 + TXT

and produces:

Standard SRT

with these guarantees:

1. Every script line becomes exactly one SRT cue.
2. SRT text exactly matches the original script line.
3. Timing is derived from WhisperX word-level forced alignment.
4. No sentence is automatically split or merged.
5. Invalid/unreliable alignment is detected instead of silently producing bad data.
6. Output passes Standard SRT validation.
7. Audio and SRT have identical basenames.
8. Batch processing is sequential and memory-safe.
9. Failed jobs can be retried.
10. Completed jobs can be resumed/skipped.
11. The entire pipeline runs locally without paid APIs or cloud services.
12. The output can be imported into me2listen without preparation-tool-specific metadata.


## 33. MOST IMPORTANT IMPLEMENTATION RULE

Do NOT build a generic speech-to-subtitle system.

Build a:

"Known English Script → Accurately Timed SRT"

system.

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
lesson-name.txt

Output:
lesson-name.mp3
lesson-name.srt

The MP3 is preserved as the original source asset.
The SRT is the only generated lesson asset.
