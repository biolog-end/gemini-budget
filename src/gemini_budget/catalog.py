"""Начальный профиль бесплатных квот одного проекта AI Studio, не глобальные квоты Google."""

PROFILE_DATE = '2026-09-18'
PROFILE_SOURCE = 'user_ai_studio'
DEFAULT_LIMITS = {
    'gemini-2.5-flash': {'rpm': 5, 'tpm': 250_000, 'rpd': 20},
    'gemini-2.5-flash-lite': {'rpm': 10, 'tpm': 250_000, 'rpd': 20},
    'gemini-3.7-flash': {'rpm': 5, 'tpm': 250_000, 'rpd': 20},
    'gemini-3-flash-preview': {'rpm': 5, 'tpm': 250_000, 'rpd': 20},
    'gemini-3.5-flash': {'rpm': 5, 'tpm': 250_000, 'rpd': 20},
    'gemini-3.8-flash': {'rpm': 5, 'tpm': 250_000, 'rpd': 20},
    'gemini-3.5-flash-lite': {'rpm': 15, 'tpm': 250_000, 'rpd': 500},
    'gemini-3.1-flash-lite': {'rpm': 15, 'tpm': 250_000, 'rpd': 500},
    'gemini-3.6-flash': {'rpm': 5, 'tpm': 250_000, 'rpd': 20},
    'gemma-4-26b-a4b-it': {'rpm': 30, 'tpm': 16_000, 'rpd': 14_400},
    'gemma-4-31b-it': {'rpm': 30, 'tpm': 16_000, 'rpd': 14_400},
    'gemini-2.5-pro': {'rpm': 0, 'tpm': 0, 'rpd': 0},
    'gemini-3.1-pro-preview': {'rpm': 0, 'tpm': 0, 'rpd': 0},
    'gemini-2.5-flash-preview-tts': {'rpm': 3, 'tpm': 10_000, 'rpd': 10},
    'gemini-3.1-flash-tts-preview': {'rpm': 3, 'tpm': 10_000, 'rpd': 10},
    'gemini-2.5-pro-preview-tts': {'rpm': 0, 'tpm': 0, 'rpd': 0},
    'gemini-3.5-transcribe': {'rpm': 3, 'tpm': 10_000, 'rpd': 25},
    'gemini-3.5-transcribe-live': {'rpm': None, 'tpm': 20_000, 'rpd': None},
}
MODEL_LABELS = {
    'gemini-2.5-flash': 'Gemini 2.5 Flash',
    'gemini-2.5-flash-lite': 'Gemini 2.5 Flash Lite',
    'gemini-3.7-flash': 'Gemini 3.7 Flash',
    'gemini-3-flash-preview': 'Gemini 3 Flash',
    'gemini-3.5-flash': 'Gemini 3.5 Flash',
    'gemini-3.8-flash': 'Gemini 3.8 Flash',
    'gemini-3.5-flash-lite': 'Gemini 3.5 Flash Lite',
    'gemini-3.1-flash-lite': 'Gemini 3.1 Flash Lite',
    'gemini-3.6-flash': 'Gemini 3.6 Flash',
    'gemma-4-26b-a4b-it': 'Gemma 4 26B',
    'gemma-4-31b-it': 'Gemma 4 31B',
    'gemini-2.5-pro': 'Gemini 2.5 Pro',
    'gemini-3.1-pro-preview': 'Gemini 3.1 Pro',
    'gemini-2.5-flash-preview-tts': 'Gemini 2.5 Flash TTS',
    'gemini-3.1-flash-tts-preview': 'Gemini 3.1 Flash TTS',
    'gemini-2.5-pro-preview-tts': 'Gemini 2.5 Pro TTS',
    'gemini-3.5-transcribe': 'Gemini 3.5 Transcribe',
    'gemini-3.5-transcribe-live': 'Gemini 3.5 Transcribe Live',
}

MODEL_TASKS = {model: ('tts' if 'tts' in model else 'transcription' if 'transcribe' in model else 'chat')
               for model in DEFAULT_LIMITS}
CHAT_MODEL_IDS = tuple(model for model in DEFAULT_LIMITS if MODEL_TASKS[model] == 'chat')


def has_free_quota(model):
    value = DEFAULT_LIMITS.get(model)
    return value is not None and all(limit is None or limit > 0 for limit in value.values())
