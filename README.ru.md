# gemini_budget

[English](README.md) | **Русский**

Общий учёт квот Gemini для всех проектов текущего пользователя плюс каталог моделей
Gemini (цены, бесплатные лимиты, размышления, Google Search). Несколько приложений с
одним API-ключом видят одни счётчики; обновление каталога доходит до всех программ
одним `pip install -U`. Без зависимостей: не нужны ни Google SDK, ни Flask.

## Установка

```bat
pip install git+https://github.com/biolog-end/gemini-budget.git
```

Для разработки — редактируемая копия:

```bat
pip install -e путь\к\gemini-budget
```

Состояние хранится в `~/.gemini_budget/state.json`. Переменная `GEMINI_BUDGET_DIR`
переносит его сразу для всех проектов.

## Каталог

```python
import gemini_budget as gb

gb.models()                                 # все модели переписки (квоты, цены, thinking, Search)
gb.models(task='tts')                       # озвучка
gb.models(task='transcription')             # транскрипция
gb.free_models()                            # только модели с бесплатной квотой
gb.model_info('gemini-3.8-flash')           # одна строка
gb.DEFAULT_CHAT_MODEL                       # рекомендуемый дефолт переписки
gb.LIGHT_CHAT_MODEL                         # дешёвая модель для памяти/сводок
gb.is_text_model('gemini-9-flash-x')        # True для имени, похожего на чат-модель
gb.is_retired('gemini-2.0-flash')           # текст объяснения, если Google её выключил
gb.supports_thinking('gemini-3.8-flash')
gb.thinking_style('gemini-2.5-pro')         # {'style': 'budget', 'off': 128} или {'style': 'level', ...}
```

В каждой строке — `price` (`input`/`output` долларов за 1M токенов платного тарифа),
`limits` (`rpm`/`tpm`/`rpd` вашего проекта; `None` — нет бесплатной квоты),
`thinking`, `search` (`'free'` / `'paid'` / `None`), `inputs`, `context_window`,
`max_output`, `tier` и `rank` для интерфейса.

| Модели | Бесплатная квота |
| --- | --- |
| 3.8 Flash, 3.6 Flash, 3 Flash, 2.5 Flash | 20 запросов в день |
| 3.5 Flash Lite, 3.1 Flash Lite | 500 запросов в день |
| Gemma 4 26B, Gemma 4 31B | 30 RPM, 16 000 TPM, 14 400 RPD |
| 2.5 Flash Lite | 10 RPM, 20 RPD |
| 3.7 Flash, 3.5 Flash, 2.5 Pro, 3.1 Pro, 4 Argon, Nano Banana | только платный |

Цены и бесплатные строки — снимок одного проекта AI Studio на дату `PROFILE_DATE`.
Если у вашего проекта другие лимиты, поправьте их через `correct()`.

## Учёт запроса

```python
reservation, reason = gb.reserve(key, model, input_tokens=estimated_input)
if reservation is None:
    raise RuntimeError(reason)                     # перейти к следующему ключу или модели
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

- `reserve()` занимает один запрос до HTTP-вызова. Резервы учитываются в остатке,
  поэтому два проекта не займут последний запрос одновременно.
- В расход попадают только успешные ответы (`success=True`); ошибка или пустой ответ
  освобождают резерв.
- После 429 Google можно передать
  `failure={"kind": "quota", "until": unix_time, "reason": "…"}`, чтобы поставить модель
  на паузу для этого ключа. Подробный `report` поддерживает `scope` и `zero_limit`.
  В `reason` не должно быть секретов.
- RPM/TPM считаются в окне 60 секунд, RPD сбрасывается в полночь America/Los_Angeles.

У одного ключа один и тот же SHA-256-отпечаток во всех проектах, сам секрет не
сохраняется. Атомарная запись и блокировки ОС защищают состояние от одновременной
работы процессов; во время сетевого запроса блокировка не держится.

## Ручная правка

```python
gb.correct(key, model, {
    'rpm': 5, 'tpm': 250000, 'rpd': 20,
    'requests_today': 3,
    'requests_last_minute': 1, 'input_tokens_last_minute': 1200,
})
gb.clear_pause(key)                          # снять все паузы ключа
gb.clear_pause(key, 'gemini-3.8-flash')      # снять только с одной модели
```

Правка действует для всех проектов с этим ключом. Текущие резервы сохраняются, старая
пауза API снимается. Нулевой лимит выключает модель до новой правки. Строки, которые
пользователь не трогал, следуют новой `PROFILE_DATE`.

## Перенос старого журнала

`gb.import_legacy(path)` один раз для каждого исходного файла переносит старый
журнал проекта в общее состояние.

## Командная строка

```bat
gemini-budget models                 :: бесплатные модели переписки (--task tts | transcription | ...)
gemini-budget status                 :: остатки для GEMINI_API_KEY или GOOGLE_API_KEY
gemini-budget path                   :: где лежит файл состояния
```

## Соседние библиотеки

- [`openai-budget`](https://github.com/biolog-end/openai-budget) — то же для OpenAI.
- [`ai-router`](https://github.com/biolog-end/ai-router) — общее хранилище ключей и
  устойчивый слой запросов, который использует этот бюджет.
