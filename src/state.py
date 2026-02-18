from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict

# чтобы forgotten не рос бесконечно
FORGOTTEN_TTL_DAYS = 30


@dataclass
class State:
    # active: wb_id -> { seenAt, msOrderId, msOrderHref }
    active: Dict[str, dict] = field(default_factory=dict)
    # forgotten: wb_id -> { forgottenAt }
    forgotten: Dict[str, dict] = field(default_factory=dict)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_state(path: str) -> State:
    p = Path(path)
    if not p.exists():
        return State()

    raw = p.read_text(encoding="utf-8").strip()
    if not raw:
        return State()

    obj = json.loads(raw)
    return State(
        active=obj.get("active", {}) or {},
        forgotten=obj.get("forgotten", {}) or {},
    )


def save_state(path: str, state: State) -> None:
    cleanup_forgotten(state)

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(
            {"active": state.active, "forgotten": state.forgotten},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def cleanup_forgotten(state: State) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(days=FORGOTTEN_TTL_DAYS)

    to_delete = []
    for wb_id, v in state.forgotten.items():
        ts = v.get("forgottenAt")
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00")) if ts else None
        except Exception:
            dt = None

        # если дата битая/пустая — чистим
        if dt is None or dt < cutoff:
            to_delete.append(wb_id)

    for wb_id in to_delete:
        state.forgotten.pop(wb_id, None)


def is_forgotten(state: State, wb_id: str) -> bool:
    return wb_id in state.forgotten


def remember(state: State, wb_id: str, *, ms_order_id: str, ms_order_href: str) -> None:
    """
    Запоминаем только те WB id, по которым мы УСПЕШНО создали CustomerOrder.
    """
    state.active[wb_id] = {
        "seenAt": _now_iso(),
        "msOrderId": ms_order_id,
        "msOrderHref": ms_order_href,
    }


def forget_forever(state: State, wb_id: str) -> None:
    """
    По ТЗ: больше никогда не трогаем этот WB id (переживает рестарты).
    """
    state.active.pop(wb_id, None)
    state.forgotten[wb_id] = {"forgottenAt": _now_iso()}


def forget_active(state: State, wb_id: str) -> None:
    """
    Убрать из active без добавления в forgotten (на всякий случай, редко нужно).
    """
    state.active.pop(wb_id, None)
