"""Общий для независимых проектов локальный учёт Gemini и атомарные резервации."""

import hashlib
import copy
import json
import time
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import os
from pathlib import Path

from .catalog import DEFAULT_LIMITS
from .storage import file_lock, read_json, write_json


def state_path():
    """Один каталог текущего пользователя, независимо от cwd и проекта."""
    directory = os.getenv('GEMINI_BUDGET_DIR')
    return Path(directory).expanduser().resolve() / 'state.json' if directory else Path.home() / '.gemini_budget' / 'state.json'


def fingerprint(key):
    """Совпадает у одного ключа во всех инстансах; секрет в журнал не попадает."""
    return hashlib.sha256(key.strip().encode('utf-8')).hexdigest()


def canonical_model(model):
    return (model or '').removeprefix('models/')


def _calendar(now):
    try:
        pacific = ZoneInfo('America/Los_Angeles')
    except Exception:
        # Windows без tzdata: даты перехода США на летнее/зимнее время.
        utc = datetime.fromtimestamp(now, timezone.utc)
        def offset(instant):
            march = datetime(instant.year, 3, 8, 10, tzinfo=timezone.utc)
            march += timedelta(days=(6 - march.weekday()) % 7)
            november = datetime(instant.year, 11, 1, 9, tzinfo=timezone.utc)
            november += timedelta(days=(6 - november.weekday()) % 7)
            return -7 if march <= instant < november else -8
        local = utc + timedelta(hours=offset(utc))
        next_date = (local + timedelta(days=1)).date()
        candidate = datetime(next_date.year, next_date.month, next_date.day, tzinfo=timezone.utc)
        midnight = candidate - timedelta(hours=offset(candidate + timedelta(hours=8)))
        return local.date().isoformat(), midnight.timestamp()
    local = datetime.fromtimestamp(now, pacific)
    midnight = (local + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return local.date().isoformat(), midnight.timestamp()


def _load(state_file):
    # Повреждённый журнал нельзя молча обнулить: это откроет исчерпанные квоты.
    data = read_json(state_file, {'version': 1, 'keys': {}})
    if not isinstance(data, dict) or not isinstance(data.get('keys'), dict):
        raise ValueError('Журнал лимитов Gemini повреждён.')
    return data


def _row(data, key, model, now):
    models = data['keys'].setdefault(fingerprint(key), {}).setdefault('models', {})
    row = models.setdefault(model, {})
    return _normalize_row(row, model, now)


def _normalize_row(row, model, now):
    row.setdefault('limits', DEFAULT_LIMITS.get(model, {'rpm': None, 'tpm': None, 'rpd': None}).copy())
    row.setdefault('revision', 0)
    day, _ = _calendar(now)
    if row.get('day') != day:
        row.update(day=day, requests_today=0, successful_today=0)
    row['minute'] = [hit for hit in row.get('minute', []) if hit['at'] > now - 60]
    row['pending'] = {rid: item for rid, item in row.get('pending', {}).items()
                      if item['at'] > now - 600}
    if row.get('accounting_version', 1) < 2:
        # Старый журнал считал попытки. Достоверны только сохранённые успехи;
        # у старых минутных записей нет признака успеха, сохраняем лишь текущий резерв.
        row['requests_today'] = row.get('successful_today', 0)
        row['minute'] = [hit for hit in row['minute'] if hit.get('id') in row['pending']]
        row['accounting_version'] = 2
    return row


def _view(row, model, now):
    limits = row['limits']
    minute = row['minute']
    requests = sum(hit.get('requests', 1) for hit in minute if hit.get('id') not in row['pending'])
    tokens = sum(hit.get('tokens', 0) for hit in minute if hit.get('id') not in row['pending'])
    reserved_requests = sum(item['day'] == row['day'] for item in row['pending'].values())
    reserved_minute = sum(hit.get('requests', 1) for hit in minute if hit.get('id') in row['pending'])
    reserved_tokens = sum(hit.get('tokens', 0) for hit in minute if hit.get('id') in row['pending'])
    used = row.get('requests_today', 0)
    day, reset_at = _calendar(now)
    reason, until = '', 0
    if row.get('blocked_until', 0) > now:
        reason, until = row.get('block_reason', 'Пауза после ответа Google'), row['blocked_until']
    elif any(limits.get(name) == 0 for name in ('rpm', 'tpm', 'rpd')):
        zero = ', '.join(name.upper() for name in ('rpm', 'tpm', 'rpd') if limits.get(name) == 0)
        reason = f'Нулевая квота {zero} в настройках этого ключа. Измените лимит, чтобы включить модель.'
    elif limits.get('rpd') is not None and used + reserved_requests >= limits['rpd']:
        reason, until = f"Запросы на этот ключ для {model} закончились на сегодня ({used}/{limits['rpd']})", reset_at
        if reserved_requests and used < limits['rpd']:
            reason, until = 'Оставшиеся дневные запросы временно заняты текущими генерациями', 0
    elif limits.get('rpm') is not None and requests + reserved_minute >= limits['rpm']:
        reason = f"Исчерпан лимит запросов в минуту ({requests}/{limits['rpm']})"
        until = min((hit['at'] + 60 for hit in minute), default=now + 60)
    elif limits.get('tpm') is not None and tokens + reserved_tokens >= limits['tpm']:
        reason = f"Исчерпан лимит входных токенов в минуту ({tokens}/{limits['tpm']})"
        until = min((hit['at'] + 60 for hit in minute), default=now + 60)
    return {
        'model': model, 'day': day, 'limits': dict(limits),
        'requests_last_minute': requests, 'input_tokens_last_minute': tokens,
        'requests_today': used, 'successful_today': row.get('successful_today', 0),
        'remaining_minute': max(0, limits['rpm'] - requests - reserved_minute) if limits.get('rpm') is not None else None,
        'remaining_tokens_minute': max(0, limits['tpm'] - tokens - reserved_tokens) if limits.get('tpm') is not None else None,
        'remaining_day': (0 if row.get('blocked_until', 0) > now and row.get('blocked_scope') == 'day'
                          else max(0, limits['rpd'] - used - reserved_requests)) if limits.get('rpd') is not None else None,
        'reserved_day': reserved_requests, 'reserved_minute': reserved_minute, 'reserved_tokens_minute': reserved_tokens,
        'in_flight': len(row['pending']), 'blocked': bool(reason), 'reason': reason,
        'left_s': max(0, int(until - now + 1)) if reason and until else 0,
        'reset_at': reset_at, 'revision': row['revision'],
    }


def snapshots(keys, *, state_file=None):
    """Снимки ключей вызывающего проекта, но расходы общие. Без сетевых запросов."""
    state_file = str(state_file or state_path())
    now = time.time()
    with file_lock(state_file):
        data = _load(state_file)
        result = {}
        for entry in keys:
            existing = data['keys'].get(fingerprint(entry['key']), {}).get('models', {})
            models = list(dict.fromkeys([*DEFAULT_LIMITS, *existing]))
            result[entry['id']] = [_view(_row(data, entry['key'], model, now), model, now)
                                    for model in models]
        return result


def reserve(key, model, input_tokens=0, *, state_file=None):
    """Атомарно занимает квоту перед HTTP-запросом; блокировка не держится в сети."""
    model = canonical_model(model)
    state_file = str(state_file or state_path())
    now = time.time()
    with file_lock(state_file):
        data = _load(state_file)
        row = _row(data, key, model, now)
        status = _view(row, model, now)
        if status['blocked']:
            wait = f"; повторная проверка через {status['left_s']} с" if status['left_s'] else ''
            return None, status['reason'] + wait
        estimate = max(0, int(input_tokens or 0))
        tpm = row['limits'].get('tpm')
        if tpm is not None and status['input_tokens_last_minute'] + status['reserved_tokens_minute'] + estimate > tpm:
            return None, f'Запрос не помещается в TPM {model}: примерно {estimate} входных токенов, осталось {status["remaining_tokens_minute"]}'
        rid = uuid.uuid4().hex
        item = {'at': now, 'day': row['day'], 'tokens': estimate, 'revision': row['revision']}
        row['pending'][rid] = item
        row['minute'].append({'id': rid, 'at': now, 'tokens': estimate})
        write_json(state_file, data)
        return rid, None


def finish(key, model, reservation, success=False, input_tokens=None, failure=None, *, state_file=None):
    """Успешный ответ занимает квоту; ошибка освобождает предварительный резерв."""
    if not reservation:
        return
    model = canonical_model(model)
    state_file = str(state_file or state_path())
    now = time.time()
    with file_lock(state_file):
        data = _load(state_file)
        row = _row(data, key, model, now)
        pending = row['pending'].pop(reservation, None)
        if pending and success and pending['day'] == row['day']:
            row['successful_today'] += 1
            row['requests_today'] += 1
        if pending and not success:
            row['minute'] = [hit for hit in row['minute'] if hit.get('id') != reservation]
        if pending and success:
            amount = max(0, int(input_tokens)) if input_tokens is not None else pending['tokens']
            hit = next((hit for hit in row['minute'] if hit.get('id') == reservation), None)
            if hit is None:
                row['minute'].append({'id': reservation, 'at': now, 'tokens': amount})
            else:
                hit.update(at=now, tokens=amount)
        # Правка счётчиков отменяет старые паузы даже при ответе старого запроса.
        if (failure and pending and pending['revision'] == row['revision']
                and failure.get('kind') in ('quota', 'model_unavailable')):
            report = failure.get('report') or {}
            daily_exhausted = report.get('scope') == 'day' and not report.get('zero_limit')
            # Старый ответ о дневной квоте не закрывает уже начавшиеся новые сутки.
            if ((not daily_exhausted or pending['day'] == row['day'])
                    and failure.get('until', 0) > now):
                row['blocked_until'] = failure['until']
                row['block_reason'] = failure.get('reason', 'Пауза после ответа Google')
                row['blocked_scope'] = report.get('scope', 'unknown')
        write_json(state_file, data)


def correct(key, model, values, *, state_file=None):
    """Ручная коррекция одной строки, без потери запросов других процессов."""
    model = canonical_model(model)
    if model not in DEFAULT_LIMITS:
        raise ValueError('Ручная таблица содержит только модели с указанными бесплатными квотами.')
    names = ('rpm', 'tpm', 'rpd', 'requests_today',
             'requests_last_minute', 'input_tokens_last_minute')
    parsed = {}
    for name in names:
        value = values.get(name)
        if isinstance(value, bool) or not str(value).isdigit():
            raise ValueError('Счётчики и лимиты должны быть целыми неотрицательными числами.')
        parsed[name] = int(value)
    state_file = str(state_file or state_path())
    now = time.time()
    with file_lock(state_file):
        data = _load(state_file)
        row = _row(data, key, model, now)
        pending_hits = [hit for hit in row['minute'] if hit.get('id') in row['pending']]
        row['limits'] = {name: parsed[name] for name in ('rpm', 'tpm', 'rpd')}
        row['requests_today'] = parsed['requests_today']
        row['successful_today'] = parsed['requests_today']
        row['minute'] = pending_hits
        if parsed['requests_last_minute'] or parsed['input_tokens_last_minute']:
            row['minute'].append({'at': now, 'requests': parsed['requests_last_minute'],
                                  'tokens': parsed['input_tokens_last_minute']})
        row.update(blocked_until=0, block_reason='', blocked_scope='', revision=row['revision'] + 1)
        write_json(state_file, data)
        return _view(row, model, now)


def import_legacy(path, *, state_file=None):
    """Однократно переносит журнал проекта в общий, не удаляя исходный файл."""
    from contextlib import ExitStack

    source = Path(path).resolve()
    target = Path(state_file or state_path()).resolve()
    if source == target or not source.exists():
        return False
    source_id = hashlib.sha256(os.path.normcase(str(source)).encode('utf-8')).hexdigest()
    now = time.time()
    with ExitStack() as stack:
        for locked_path in sorted((str(source), str(target))):
            stack.enter_context(file_lock(locked_path))
        data = _load(target)
        imported = data.setdefault('imports', {})
        if source_id in imported:
            return False
        legacy = read_json(source)
        if not isinstance(legacy, dict) or not isinstance(legacy.get('keys'), dict):
            raise ValueError('Старый журнал лимитов Gemini повреждён.')
        for key_hash, key_data in legacy['keys'].items():
            if len(key_hash) != 64 or any(c not in '0123456789abcdef' for c in key_hash):
                raise ValueError('Старый журнал содержит некорректный идентификатор ключа.')
            models = data['keys'].setdefault(key_hash, {}).setdefault('models', {})
            for model, old in key_data['models'].items():
                model = canonical_model(model)
                old = _normalize_row(copy.deepcopy(old), model, now)
                if model not in models:
                    models[model] = old
                    continue
                current = _normalize_row(models[model], model, now)
                # Копия проекта могла содержать ту же историю: не складываем её дважды.
                current['requests_today'] = max(current['requests_today'], old['requests_today'])
                current['successful_today'] = max(current['successful_today'], old['successful_today'])
                seen = {hit.get('id') or json.dumps(hit, sort_keys=True) for hit in current['minute']}
                for hit in old['minute']:
                    identity = hit.get('id') or json.dumps(hit, sort_keys=True)
                    if identity not in seen:
                        current['minute'].append(hit)
                        seen.add(identity)
                for rid, item in old['pending'].items():
                    current['pending'].setdefault(rid, dict(item, revision=current['revision']))
                # Явная правка в общем журнале имеет приоритет над старой паузой.
                if not current['revision'] and old.get('blocked_until', 0) > current.get('blocked_until', 0):
                    current['blocked_until'] = old['blocked_until']
                    current['block_reason'] = old.get('block_reason', 'Пауза после ответа Google')
        imported[source_id] = {'at': now}
        write_json(target, data)
        return True
