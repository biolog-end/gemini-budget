"""Каталог моделей Gemini: бесплатные квоты одного проекта AI Studio, цены и возможности.

Квоты — снимок таблицы Rate limits проекта пользователя, не глобальное обещание Google.
Модель есть в таблице → у неё есть `limits` (нули означают «только платно»). Модели,
которых в таблице нет, но которые ещё отдаёт `models.list()`, остаются в каталоге с
`limits=None`: бесплатной квоты у них нет, платный проект может ими пользоваться.
Цены — платный тариф, доллары за 1M токенов, промпт до 200k; None — цена неизвестна.
"""

import re

PROFILE_DATE = '2026-10-25'
PROFILE_SOURCE = 'user_ai_studio'
PRICES_CHECKED = '2026-09-18'

_FLASH = {'rpm': 5, 'tpm': 250_000, 'rpd': 20}
_LITE = {'rpm': 15, 'tpm': 250_000, 'rpd': 500}
_GEMMA = {'rpm': 30, 'tpm': 16_000, 'rpd': 14_400}
_TTS = {'rpm': 3, 'tpm': 10_000, 'rpd': 10}
_EMBEDDING = {'rpm': 100, 'tpm': 30_000, 'rpd': 1_000}
_ZERO = {'rpm': 0, 'tpm': 0, 'rpd': 0}

# Как модель отключает размышления: уровень 3.x/Gemma 4 или бюджет 2.5.
_LEVEL = {'style': 'level', 'off': 'MINIMAL'}
_LEVEL_PRO = {'style': 'level', 'off': 'LOW'}
_BUDGET = {'style': 'budget', 'off': 0}
_BUDGET_PRO = {'style': 'budget', 'off': 128}

_MEDIA = ('text', 'image', 'audio', 'video', 'pdf')


def _chat(model_id, label, limits, price_in, price_out, thinking, *, family, status='stable',
          search='paid', inputs=_MEDIA, context=1_048_576, max_output=65_536, tier=None, rank=999, note=''):
    return {'id': model_id, 'label': label, 'task': 'chat', 'limits': limits,
            'price': {'input': price_in, 'output': price_out}, 'thinking': thinking,
            'search': search, 'inputs': inputs, 'context_window': context, 'max_output': max_output,
            'family': family, 'status': status, 'tier': tier, 'rank': rank, 'note': note}


def _other(model_id, label, task, limits, note='', status='stable'):
    return {'id': model_id, 'label': label, 'task': task, 'limits': limits,
            'price': {'input': None, 'output': None}, 'thinking': None, 'search': None,
            'inputs': None, 'context_window': None, 'max_output': None, 'family': None,
            'status': status, 'tier': None, 'rank': 999, 'note': note}


MODELS = [
    _chat('gemini-3.8-flash', 'Gemini 3.8 Flash', _FLASH, 0.75, 3.75, _LEVEL, family='3.x',
          tier='strong', rank=1, note='Самая сильная бесплатная Flash-модель.'),
    _chat('gemini-3.6-flash', 'Gemini 3.6 Flash', _FLASH, 0.75, 3.75, _LEVEL, family='3.x',
          tier='strong', rank=2, note='Есть бесплатный тариф.'),
    _chat('gemini-3-flash-preview', 'Gemini 3 Flash', _FLASH, 0.50, 3.00, _LEVEL, family='3.x',
          status='preview', tier='strong', rank=3, note='Preview; Google рекомендует переход на 3.6/3.8 Flash.'),
    _chat('gemini-2.5-flash', 'Gemini 2.5 Flash', _FLASH, 0.30, 2.50, _BUDGET, family='2.5',
          search='free', tier='strong', rank=4,
          note='Доступ новых проектов к 2.5 может быть ограничен Google.'),
    _chat('gemini-3.5-flash-lite', 'Gemini 3.5 Flash Lite', _LITE, 0.30, 2.50, _LEVEL, family='3.x',
          tier='light', rank=5, note='500 запросов в день — основной рабочий вариант для частых вызовов.'),
    _chat('gemini-3.1-flash-lite', 'Gemini 3.1 Flash Lite', _LITE, 0.25, 1.50, _LEVEL, family='3.x',
          tier='light', rank=6, note='Самая дешёвая из 3.x, 500 запросов в день.'),
    _chat('gemma-4-31b-it', 'Gemma 4 31B', _GEMMA, 0, 0, _LEVEL, family='Gemma 4', search=None,
          inputs=('text', 'image'), context=262_144, max_output=32_768, tier='light', rank=7,
          note='14 400 запросов в день, но всего 16 тыс. входных токенов в минуту. Без Google Search.'),
    _chat('gemma-4-26b-a4b-it', 'Gemma 4 26B', _GEMMA, 0, 0, _LEVEL, family='Gemma 4', search=None,
          inputs=('text', 'image'), context=262_144, max_output=32_768, tier='light', rank=8,
          note='14 400 запросов в день, но всего 16 тыс. входных токенов в минуту. Без Google Search.'),
    _chat('gemini-2.5-flash-lite', 'Gemini 2.5 Flash Lite', {'rpm': 10, 'tpm': 250_000, 'rpd': 20},
          0.10, 0.40, _BUDGET, family='2.5', search='free', tier='light', rank=9,
          note='Доступ новых проектов к 2.5 может быть ограничен Google.'),
    _chat('gemini-4-argon', 'Gemini 4 Argon', _ZERO, None, None, _LEVEL, family='4', status='new',
          max_output=32_768, tier='paid', rank=10, note='Новое поколение; бесплатной квоты нет, цена не опубликована.'),
    _chat('gemini-3.1-pro-preview', 'Gemini 3.1 Pro', _ZERO, 2.00, 12.00, _LEVEL_PRO, family='3.x',
          status='preview', tier='paid', rank=11, note='Флагман; только платный проект.'),
    _chat('gemini-2.5-pro', 'Gemini 2.5 Pro', _ZERO, 1.25, 10.00, _BUDGET_PRO, family='2.5',
          tier='paid', rank=12, note='Только платный проект.'),
    _chat('gemini-3.7-flash', 'Gemini 3.7 Flash', None, 0.75, 3.75, _LEVEL, family='3.x',
          tier='paid', rank=13, note='С 25.10.2026 нет в таблице бесплатных квот; API модель ещё отдаёт.'),
    _chat('gemini-3.5-flash', 'Gemini 3.5 Flash', None, 1.50, 9.00, _LEVEL, family='3.x',
          tier='paid', rank=14, note='С 25.10.2026 нет в таблице бесплатных квот; API модель ещё отдаёт.'),

    _other('gemini-3.8-flash-tts', 'Gemini 3.8 Flash TTS', 'tts', _TTS),
    _other('gemini-3.8-flash-lite-tts', 'Gemini 3.8 Flash Lite TTS', 'tts', _TTS),
    _other('gemini-3.1-flash-tts-preview', 'Gemini 3.1 Flash TTS', 'tts', _TTS, status='preview'),
    _other('gemini-2.5-flash-preview-tts', 'Gemini 2.5 Flash TTS', 'tts', _TTS, status='preview'),
    _other('gemini-2.5-pro-preview-tts', 'Gemini 2.5 Pro TTS', 'tts', _ZERO, status='preview'),
    _other('gemini-3.5-transcribe', 'Gemini 3.5 Transcribe', 'transcription', {'rpm': 3, 'tpm': 10_000, 'rpd': 25}),
    _other('gemini-3.5-transcribe-live', 'Gemini 3.5 Transcribe Live', 'transcription',
           {'rpm': None, 'tpm': 20_000, 'rpd': None}, note='Live API.'),
    _other('gemini-embedding-001', 'Gemini Embedding 1', 'embedding', _EMBEDDING),
    _other('gemini-embedding-2', 'Gemini Embedding 2', 'embedding', _EMBEDDING),
    _other('gemini-3.8-live', 'Gemini 3.8 Live', 'live', {'rpm': None, 'tpm': 65_000, 'rpd': None}),
    _other('gemini-3.8-live-extended-thinking', 'Gemini 3.8 Live Extended Thinking', 'live',
           {'rpm': None, 'tpm': 65_000, 'rpd': None}),
    _other('gemini-3.1-flash-live-preview', 'Gemini 3 Flash Live', 'live',
           {'rpm': None, 'tpm': 65_000, 'rpd': None}, status='preview'),
    _other('gemini-3.5-live-translate-preview', 'Gemini 3.5 Live Translate', 'live',
           {'rpm': None, 'tpm': 20_000, 'rpd': None}, status='preview'),
    _other('gemini-2.5-flash-native-audio-latest', 'Gemini 2.5 Flash Native Audio Dialog', 'live',
           {'rpm': None, 'tpm': 1_000_000, 'rpd': None}),
    _other('antigravity-preview-latest', 'Antigravity', 'agent', {'rpm': 60, 'tpm': 100_000, 'rpd': 100},
           status='preview'),
    _other('deep-research-pro-preview-12-2025', 'Deep Research Pro Preview', 'agent', _ZERO, status='preview'),
    _other('gemini-2.5-computer-use-preview-10-2025', 'Computer Use Preview', 'agent', _ZERO, status='preview'),
    _other('gemini-robotics-er-2-preview', 'Gemini Robotics ER 2 Preview', 'robotics', _FLASH, status='preview'),
    _other('gemini-2.5-flash-image', 'Nano Banana', 'image', _ZERO),
    _other('gemini-3-pro-image', 'Nano Banana Pro', 'image', _ZERO),
    _other('gemini-3.1-flash-image', 'Nano Banana 2', 'image', _ZERO),
    _other('gemini-3.1-flash-lite-image', 'Nano Banana 2 Lite', 'image', _ZERO),
    _other('gemini-nano-banana-2.1', 'Gemini Nano Banana 2.1', 'image', _ZERO),
    _other('gemini-omni-1.1-flash', 'Gemini Omni 1.1 Flash', 'multimodal', _ZERO),
    _other('lyria-3-clip-preview', 'Lyria 3 Clip', 'music', _ZERO, status='preview'),
    _other('lyria-3-pro-preview', 'Lyria 3 Pro', 'music', _ZERO, status='preview'),
]

# Отключены Google: обращение вернёт 404.
RETIRED_MODELS = {
    'gemini-3-pro-preview': 'Отключена Google 09.03.2026. Замена: gemini-3.1-pro-preview (платная).',
    'gemini-2.0-flash': 'Отключена Google. Замена: gemini-2.5-flash или gemini-3.6-flash.',
    'gemini-2.0-flash-lite': 'Отключена Google. Замена: gemini-3.5-flash-lite.',
    'gemini-2.0-flash-exp': 'Отключена Google. Замена: gemini-3.6-flash.',
    'gemini-1.5-pro': 'Отключена Google. Замена: gemini-2.5-pro.',
    'gemini-1.5-flash': 'Отключена Google. Замена: gemini-3.6-flash.',
    'gemini-1.5-flash-8b': 'Отключена Google. Замена: gemini-3.5-flash-lite.',
    'gemini-pro': 'Устаревшее имя. Замена: gemini-2.5-pro.',
}

DEFAULT_CHAT_MODEL = 'gemini-3.6-flash'
LIGHT_CHAT_MODEL = 'gemini-3.5-flash-lite'

MODELS_BY_ID = {model['id']: model for model in MODELS}
DEFAULT_LIMITS = {model['id']: dict(model['limits']) for model in MODELS if model['limits'] is not None}
MODEL_LABELS = {model['id']: model['label'] for model in MODELS}
MODEL_TASKS = {model['id']: model['task'] for model in MODELS}
CHAT_MODEL_IDS = tuple(model['id'] for model in MODELS if model['task'] == 'chat')

# Умеют generateContent, но не годятся для переписки: озвучка, картинки, музыка, агенты.
_NON_TEXT_MARKERS = (
    'tts', 'image', 'nano-banana', 'omni', 'transcribe', 'lyria', 'robotics', 'computer-use',
    'antigravity', 'deep-research', 'embedding', 'veo', 'live', 'native-audio', 'aqa', 'imagen',
)


def base_model(model):
    """'models/gemini-2.0-flash-001' → 'gemini-2.0-flash': для поиска в каталоге."""
    name = (model or '').strip().lower().removeprefix('models/')
    return re.sub(r'-\d{3}$', '', name)


def model_info(model):
    """Копия записи каталога или None."""
    info = MODELS_BY_ID.get(base_model(model)) or MODELS_BY_ID.get((model or '').strip().removeprefix('models/'))
    if info is None:
        return None
    return {**info, 'limits': dict(info['limits']) if info['limits'] is not None else None,
            'price': dict(info['price']),
            'thinking': dict(info['thinking']) if info['thinking'] else None}


def is_retired(model):
    """Текст объяснения, если модель отключена Google, иначе None."""
    return RETIRED_MODELS.get(base_model(model))


def is_text_model(model):
    """Годится ли модель (в том числе незнакомая) для текстовой переписки."""
    info = MODELS_BY_ID.get(base_model(model))
    if info is not None:
        return info['task'] == 'chat'
    name = base_model(model)
    return name.startswith(('gemini-', 'gemma-')) and not any(marker in name for marker in _NON_TEXT_MARKERS)


def thinking_style(model):
    """{'style': 'level'|'budget', 'off': …} или None, если размышлений нет.

    Незнакомые модели угадываются по имени: бюджет у 2.5, уровень у 3.x, 4.x и Gemma 4.
    """
    info = MODELS_BY_ID.get(base_model(model))
    if info is not None:
        return dict(info['thinking']) if info['thinking'] else None
    name = base_model(model)
    if name.startswith('gemini-2.5'):
        return dict(_BUDGET_PRO if '-pro' in name else _BUDGET)
    generation = re.match(r'(?:gemini|gemma)-(\d+)', name)
    if generation and int(generation.group(1)) >= (4 if name.startswith('gemma') else 3):
        return dict(_LEVEL_PRO if '-pro' in name else _LEVEL)
    return None


def supports_thinking(model):
    return thinking_style(model) is not None


def has_free_quota(model):
    value = DEFAULT_LIMITS.get(model)
    return value is not None and all(limit is None or limit > 0 for limit in value.values())
