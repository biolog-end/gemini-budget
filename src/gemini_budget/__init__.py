"""Общие квоты Gemini для независимых проектов текущего пользователя."""

from .catalog import DEFAULT_LIMITS, MODEL_LABELS, MODEL_TASKS, CHAT_MODEL_IDS, PROFILE_DATE, PROFILE_SOURCE, has_free_quota
from .core import canonical_model, correct, fingerprint, finish, import_legacy, reserve, snapshots, state_path

__version__ = '0.2.0'


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
    """Профиль с типами задач и лимитами; task='chat'/'tts'/'transcription'."""
    configured = {row['model']: row['limits'] for row in status(key, state_file=state_file)} if key is not None else DEFAULT_LIMITS
    return [{'id': model, 'label': MODEL_LABELS[model],
             'task': MODEL_TASKS[model],
             'free_tier': all(cap is None or cap > 0 for cap in configured[model].values()),
             'limits': dict(configured[model]), 'profile_date': PROFILE_DATE,
             'profile_source': PROFILE_SOURCE} for model in DEFAULT_LIMITS
            if task is None or MODEL_TASKS[model] == task]


def free_models(key=None, *, task='chat', state_file=None):
    """Доступные бесплатные модели для выбранного типа задач (по умолчанию переписка)."""
    return [row for row in models(key, task=task, state_file=state_file) if row['free_tier']]


__all__ = ['DEFAULT_LIMITS', 'CHAT_MODEL_IDS', 'PROFILE_DATE', 'PROFILE_SOURCE', 'canonical_model',
           'correct', 'fingerprint', 'finish', 'free_models', 'import_legacy',
           'limits', 'models', 'reserve', 'snapshots', 'state_path', 'status', 'has_free_quota']
