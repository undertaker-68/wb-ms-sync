from __future__ import annotations
import sys
from datetime import datetime

def _ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def info(msg: str) -> None:
    print(f"[{_ts()}] INFO  {msg}", flush=True)

def warn(msg: str) -> None:
    print(f"[{_ts()}] WARN  {msg}", file=sys.stderr, flush=True)

def error(msg: str) -> None:
    print(f"[{_ts()}] ERROR {msg}", file=sys.stderr, flush=True)
