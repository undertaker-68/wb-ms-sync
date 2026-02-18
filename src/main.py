from __future__ import annotations

import time
from datetime import datetime

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
        t0 = time.time()
        log.info(f"Tick: active={len(state.active)} forgotten={len(state.forgotten)}")
        try:
            sync_once(cfg, state)
            save_state(cfg.STATE_PATH, state)
        except Exception as e:
            log.error(f"Loop error: {e}")
        dt = time.time() - t0
        log.info(f"Tick done in {dt:.2f}s, sleep {cfg.POLL_SECONDS}s")
        time.sleep(cfg.POLL_SECONDS)


if __name__ == "__main__":
    main()
