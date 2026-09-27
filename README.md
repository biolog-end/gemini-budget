# gemini_budget

**English** | [Русский](README.ru.md)

Shared Gemini API quota accounting for all projects of the current user. Several apps
that use the same API keys see one set of counters, so together they do not overrun the
free tier. No dependencies: it does not need the Google SDK, Flask or anything else.

## Installation

```bat
pip install git+https://github.com/biolog-end/gemini-budget.git
```

For development, install an editable copy:

```bat
pip install -e path\to\gemini-budget
```

State lives in `~/.gemini_budget/state.json` (`%USERPROFILE%\.gemini_budget` on
Windows). Set `GEMINI_BUDGET_DIR` to move it for every project at once. Each virtual
environment installs the package separately, but all of them share one state file.
Functions also accept `state_file=...` for isolated tests.

## Models and limits

```python
import gemini_budget as gb

models = gb.free_models()                         # chat models with a free quota: id, label, task, limits
voices = gb.free_models(task='tts')               # speech synthesis models
speech = gb.free_models(task='transcription')     # transcription models
catalog = gb.models()                             # the whole profile, zero quotas included
default = gb.limits('gemini-3.8-flash')           # rpm, tpm, rpd
configured = gb.limits('gemini-3.8-flash', key)   # including manual edits for this key
rows = gb.status(key)                             # everything left for this key
row = gb.status(key, 'gemini-3.8-flash')          # a single model
```

The built-in profile is a snapshot of the free quotas of one AI Studio project taken on
2026-09-18. It is not a promise from Google for every account: if your project has
different limits, adjust them with `correct()`.

| Models | Free quota |
| --- | --- |
| 2.5 Flash, 2.5 Flash Lite, 3 Flash, 3.5 Flash, 3.6 Flash, 3.7 Flash, 3.8 Flash | 20 requests per day |
| 3.5 Flash Lite, 3.1 Flash Lite | 500 requests per day |
| Gemma 4 26B, Gemma 4 31B | 30 RPM, 16,000 TPM, 14,400 requests per day |
| 2.5 Pro, 3.1 Pro, 2.5 Pro TTS | none |

Gemini chat models have 250,000 input TPM. Separate profiles cover speech synthesis and
transcription; those are not chat models. All functions return copies.

## Accounting a request

```python
model = 'gemini-3.8-flash'
reservation, reason = gb.reserve(key, model, input_tokens=estimated_input)
if reservation is None:
    raise RuntimeError(reason)                    # try the next key or model
try:
    response = client.models.generate_content(model=model, contents=contents)
except Exception:
    gb.finish(key, model, reservation, success=False)
    raise
else:
    usage = response.usage_metadata
    gb.finish(key, model, reservation, success=True,
              input_tokens=getattr(usage, 'prompt_token_count', None))
```

- `reserve()` holds one request and the estimated input tokens before the HTTP call.
  Reservations count against what is left, so two projects cannot take the last request
  at the same time. They are reported separately as `reserved_day`, `reserved_minute`
  and `reserved_tokens_minute`.
- Only successful replies (`success=True`) are counted; the caller decides whether a
  reply is usable. An error or an empty reply (`success=False`) releases the reservation
  and changes neither RPM, TPM nor RPD. The minute window of a success starts when the
  reply arrives.
- After an API error you may pass
  `failure={"kind": "quota", "until": unix_time, "reason": "..."}` to pause the model on
  this key. A detailed `report` supports `scope` and `zero_limit`. Never put secrets in
  `reason`. An unknown error does not pause anything by itself.
- Call `finish()` once per reservation; a repeated call does not count twice.
- RPM and TPM use a sliding 60-second window. RPD resets at Pacific midnight, with DST
  taken into account.

The same key has the same SHA-256 fingerprint in every project, and secrets are never
stored. Atomic writes and OS file locks protect the state from concurrent processes on
Windows, Linux and macOS; the lock is not held during network calls.

Only projects that call `reserve()` and `finish()` are counted. Local accounting is not
guaranteed to match Google: the server may count differently or see other apps that use
the key. The pre-request token estimate is approximate and comes from the caller.

## Manual correction

```python
gb.correct(key, model, {
    'rpm': 5, 'tpm': 250000, 'rpd': 20,
    'requests_today': 3,
    'requests_last_minute': 1, 'input_tokens_last_minute': 1200,
})
```

The correction applies to every project that uses this key. Current reservations are
kept and an earlier API pause is lifted. A zero limit disables the model for this key
until the next correction. Correcting local state does not change the real Google quota.

`requests_today` and `successful_today` are one counter of successful replies;
`correct()` still accepts `successful_today` for compatibility, but the value is set
through `requests_today`. Rows from the older v1 format keep their saved successes, and
their old per-minute attempts without a success flag are dropped; current reservations
stay.

## Migrating an old journal

`gb.import_legacy(path)` merges an older per-project usage journal into the shared state,
once per source file. Daily values are merged by maximum and matching per-minute
reservations are not duplicated, so importing a copy of the same project twice does not
double its history. The old file is left in place. Restart the projects first: running
processes keep writing to the old journal.

## Command line

```bat
gemini-budget models                 :: free chat models (--task tts | transcription)
gemini-budget status                 :: what is left for GEMINI_API_KEY or GOOGLE_API_KEY
gemini-budget path                   :: where the state file lives
```
