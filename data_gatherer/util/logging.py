from __future__ import annotations
import json, sys, time
from typing import Any
_LOG_LEVEL = 'INFO'
_LOG_FORMAT = 'json'

def configure_logging(level: str = 'INFO', format: str = 'json'):
    global _LOG_LEVEL, _LOG_FORMAT
    _LOG_LEVEL = level.upper()
    _LOG_FORMAT = format.lower()

def _should_log(level: str) -> bool:
    levels = {'DEBUG': 0, 'INFO': 1, 'WARN': 2, 'ERROR': 3}
    return levels.get(level.upper(), 1) >= levels.get(_LOG_LEVEL, 1)

def log(level: str, message: str, **fields: Any):
    if not _should_log(level):
        return
    ts = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    lvl = level.upper()
    if _LOG_FORMAT == 'json':
        rec = {'ts': ts, 'level': lvl, 'msg': message}
        if fields: rec.update(fields)
        print(json.dumps(rec, sort_keys=True), file=sys.stderr)
    else:
        extra = ' '.join(f'{k}={v}' for k,v in fields.items()) if fields else ''
        line = f"{ts} [{lvl}] {message}" + (f" {extra}" if extra else '')
        print(line, file=sys.stderr)

def debug(message: str, **fields: Any): log('debug', message, **fields)

def info(message: str, **fields: Any): log('info', message, **fields)

def warn(message: str, **fields: Any): log('warn', message, **fields)

def error(message: str, **fields: Any): log('error', message, **fields)
