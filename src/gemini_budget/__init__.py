"""Общие квоты и каталог моделей Gemini для независимых проектов текущего пользователя."""

from .catalog import (CHAT_MODEL_IDS, DEFAULT_CHAT_MODEL, DEFAULT_LIMITS, LIGHT_CHAT_MODEL, MODEL_LABELS,
                      MODEL_TASKS, MODELS, PRICES_CHECKED, PROFILE_DATE, PROFILE_SOURCE, RETIRED_MODELS,
                      base_model, has_free_quota, is_retired, is_text_model, model_info, supports_thinking,
                      thinking_style)
from .core import (canonical_model, clear_pause, correct, fingerprint, finish, import_legacy, reserve,
                   snapshots, state_path)

__version__ = '0.3.0'


def status(key, model=None, *, state_file=None):
    """Остатки одного ключа: список моделей либо одна строка, если указана модель."""
    rows = snapshots([{'id': 'key', 'key': key}], state_file=state_file)['key']
    if model is None:
        return rows
    model = canonical_model(model)
    return next((row for row in rows if row['model'] == model), None)


def limits(model, key=None, *, state_file=None):
    """Копия начальных лимитов либо общих ручных настроек конкретного ключа."""
    model = canonical_model(model)
    if key is not None:
        row = status(key, model, state_file=state_file)
        return dict(row['limits']) if row else None
    value = DEFAULT_LIMITS.get(model)
    return dict(value) if value is not None else None


def models(key=None, *, task=None, state_file=None):
    """Каталог: квоты (с правками ключа, если он указан), цены и возможности моделей.

    task: 'chat', 'tts', 'transcription', 'embedding', 'live', 'agent', 'image', … или None.
    """
    configured = {row['model']: row['limits'] for row in status(key, state_file=state_file)} \
        if key is not None else DEFAULT_LIMITS
    rows = []
    for entry in MODELS:
        if task is not None and entry['task'] != task:
            continue
        info = model_info(entry['id'])
        quota = configured.get(entry['id'])
        rows.append({**info, 'limits': dict(quota) if quota is not None else None,
                     'in_profile': entry['id'] in DEFAULT_LIMITS,
                     'free_tier': quota is not None and all(cap is None or cap > 0 for cap in quota.values()),
                     'profile_date': PROFILE_DATE, 'profile_source': PROFILE_SOURCE})
    return rows


def free_models(key=None, *, task='chat', state_file=None):
    """Доступные бесплатные модели для выбранного типа задач (по умолчанию переписка)."""
    return [row for row in models(key, task=task, state_file=state_file) if row['free_tier']]


__all__ = ['CHAT_MODEL_IDS', 'DEFAULT_CHAT_MODEL', 'DEFAULT_LIMITS', 'LIGHT_CHAT_MODEL', 'MODELS',
           'PRICES_CHECKED', 'PROFILE_DATE', 'PROFILE_SOURCE', 'RETIRED_MODELS', 'base_model',
           'canonical_model', 'clear_pause', 'correct', 'fingerprint', 'finish', 'free_models',
           'has_free_quota', 'import_legacy', 'is_retired', 'is_text_model', 'limits', 'model_info',
           'models', 'reserve', 'snapshots', 'state_path', 'status', 'supports_thinking', 'thinking_style']
