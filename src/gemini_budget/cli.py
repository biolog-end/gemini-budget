"""Каталог и локальный статус без запросов к Google. Секрет читается из окружения."""

import argparse
import json
import os

from . import free_models, state_path, status


def main():
    parser = argparse.ArgumentParser(description='Общие локальные лимиты Gemini')
    parser.add_argument('command', choices=('models', 'status', 'path'), nargs='?', default='models')
    parser.add_argument('--task', choices=('chat', 'tts', 'transcription'), default='chat')
    args = parser.parse_args()
    if args.command == 'path':
        print(state_path())
        return
    if args.command == 'status':
        key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
        if not key:
            parser.error('Для status задайте GEMINI_API_KEY или GOOGLE_API_KEY в окружении.')
        result = status(key)
    else:
        result = free_models(task=args.task)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
