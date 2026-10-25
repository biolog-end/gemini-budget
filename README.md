# gemini_budget

**English** | [Русский](README.ru.md)

Shared Gemini quota accounting for every project of the current user, plus a catalog of
Gemini models (prices, free limits, thinking mode, Google Search availability). Several
apps that use the same API key see one set of counters; a model-list update reaches
every app with one `pip install -U`. Zero dependencies: it does not need the Google
SDK, Flask or anything else.

## Install

```bat
pip install git+https://github.com/biolog-end/gemini-budget.git
```

For development, install an editable copy:

```bat
pip install -e path\to\gemini-budget
```

State lives in `~/.gemini_budget/state.json`. Set `GEMINI_BUDGET_DIR` to move it; every
project reads the same file.

## Catalog

```python
import gemini_budget as gb

gb.models()                                 # every chat model (quotas, prices, thinking, Search)
gb.models(task='tts')                       # speech synthesis
gb.models(task='transcription')             # transcription
gb.free_models()                            # only models with a free chat quota
gb.model_info('gemini-3.8-flash')           # one row
gb.DEFAULT_CHAT_MODEL                       # recommended chat default
gb.LIGHT_CHAT_MODEL                         # cheap model for memory/summaries
gb.is_text_model('gemini-9-flash-x')        # a yet-unknown model: True if its name is chat-like
gb.is_retired('gemini-2.0-flash')           # text explaining Google's retirement, or None
gb.supports_thinking('gemini-3.8-flash')
gb.thinking_style('gemini-2.5-pro')         # {'style': 'budget', 'off': 128} or {'style': 'level', ...}
```

Each row carries `price` (`input`/`output` USD per 1M tokens, paid tier), `limits`
(`rpm`/`tpm`/`rpd` for this project; `None` means "no free quota"), `thinking`,
`search` (`'free'` / `'paid'` / `None`), `inputs`, `context_window`, `max_output`,
`tier` and `rank` for the UI.

| Models | Free quota (per project of this user) |
| --- | --- |
| 3.8 Flash, 3.6 Flash, 3 Flash, 2.5 Flash | 20 requests per day |
| 3.5 Flash Lite, 3.1 Flash Lite | 500 requests per day |
| Gemma 4 26B, Gemma 4 31B | 30 RPM, 16 000 TPM, 14 400 RPD |
| 2.5 Flash Lite | 10 RPM, 20 RPD |
| 3.7 Flash, 3.5 Flash, 2.5 Pro, 3.1 Pro, 4 Argon, Nano Banana | paid only |

Prices and free rows are a snapshot of one AI Studio project taken on `PROFILE_DATE`.
If your project has different limits, adjust them with `correct()`.

## Accounting a request

```python
reservation, reason = gb.reserve(key, model, input_tokens=estimated_input)
if reservation is None:
    raise RuntimeError(reason)                     # try the next key or model
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

- `reserve()` holds one request before the HTTP call. Reservations count against what
  is left, so two projects cannot both take the last request.
- Only successful replies (`success=True`) are counted; an error or an empty reply
  releases the reservation and keeps the counters untouched.
- After a Google quota error you may pass
  `failure={"kind": "quota", "until": unix_time, "reason": "…"}` to pause the model on
  this key. A detailed `report` supports `scope` and `zero_limit`. Never put secrets in
  `reason`.
- RPM/TPM use a 60-second window. RPD resets at midnight America/Los_Angeles.

The same key has the same SHA-256 fingerprint in every project, and the secret is
never stored. Atomic writes and OS file locks protect the state from concurrent
processes; the lock is not held during network calls.

## Manual correction

```python
gb.correct(key, model, {
    'rpm': 5, 'tpm': 250000, 'rpd': 20,
    'requests_today': 3,
    'requests_last_minute': 1, 'input_tokens_last_minute': 1200,
})
gb.clear_pause(key)                          # clear every paused model of this key
gb.clear_pause(key, 'gemini-3.8-flash')      # clear only this one
```

The correction applies to every project that uses this key. Current reservations are
kept and an earlier API pause is lifted. A zero limit disables the model until the
next correction. Rows the user has not touched follow new `PROFILE_DATE` releases.

## Migrating an old journal

`gb.import_legacy(path)` merges an older per-project usage journal into the shared
state, once per source file. Daily values are merged by maximum and matching per-minute
reservations are not duplicated.

## Command line

```bat
gemini-budget models                 :: free chat models (--task tts | transcription | ...)
gemini-budget status                 :: what is left for GEMINI_API_KEY or GOOGLE_API_KEY
gemini-budget path                   :: where the state file lives
```

## Related libraries

- [`openai-budget`](https://github.com/biolog-end/openai-budget) — the same, for OpenAI.
- [`ai-router`](https://github.com/biolog-end/ai-router) — shared key vault and
  fault-tolerant request layer that drives this budget.
