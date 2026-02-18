from __future__ import annotations

import time

from .config import Config
from . import log
from .state import load_state, save_state
from .sync import sync_once


def main() -> None:
    cfg = Config()
    state = load_state(cfg.STATE_PATH)

    log.info(f"STATE_PATH={cfg.STATE_PATH}")
    log.info(f"Loaded state: active={len(state.active)} forgotten={len(state.forgotten)}")

    while True:
        try:
            sync_once(cfg, state)
            save_state(cfg.STATE_PATH, state)
        except Exception as e:
            log.error(f"Loop error: {e}")
        time.sleep(cfg.POLL_SECONDS)


if __name__ == "__main__":
    main()
