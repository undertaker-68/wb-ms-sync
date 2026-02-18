from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class Config:
    # tokens
    WB_TOKEN: str = "eyJhbGciOiJFUzI1NiIsImtpZCI6IjIwMjUwOTA0djEiLCJ0eXAiOiJKV1QifQ.eyJhY2MiOjEsImVudCI6MSwiZXhwIjoxNzg3MTU3MTY2LCJpZCI6IjAxOWM2ZjA1LWE1NjItNzdiOC1hNTE4LTg4MDVmNGI5YTdmZCIsImlpZCI6NTU1OTc3MDAsIm9pZCI6MjYwMjgzLCJzIjoxNjEyNiwic2lkIjoiMjM5OGExODAtMmNjMy00ODRiLTlmMjktODQ4Y2I4ZTk1MWI0IiwidCI6ZmFsc2UsInVpZCI6NTU1OTc3MDB9.D_jZPPz8RoqWy4VvMj3c8DBDNsLDcOSF88gVwn3e7r6Udto2-Uiysz0xLWX1804ZUW2CMATt7BLbACw-O3roMw"
    MS_TOKEN: str = "7349ecbbcbc6fc07f7c2238f6822aed63f4ddb12"

    # MS base
    MS_BASE: str = "https://api.moysklad.ru/api/remap/1.2"

    # WB -> MS реквизиты
    MS_ORG_ID: str = "12d36dcd-8b6c-11e9-9109-f8fc00176e21"
    MS_AGENT_ID: str = "4a0bcce2-4f30-11ec-0a80-06160004800a"
    MS_SALESCHANNEL_ID: str = "43f63a77-f5f3-11f0-0a80-045f000dca72"
    MS_STORE_ID: str = "396769c2-5bb6-11ef-0a80-01cc000c63a9"

    # MS states for CustomerOrder
    MS_STATE_NEW: str = "12ee6581-8b6c-11e9-9109-f8fc00176e47"
    MS_STATE_SHIPPED: str = "0f8479d9-dd88-11ec-0a80-01ef0002f977"
    MS_STATE_AWAIT_ASSEMBLY: str = "ffb88772-9fd0-11ee-0a80-0641000f3d5f"
    MS_STATE_AWAIT_SHIPMENT: str = "ffbc9d6b-9fd0-11ee-0a80-0641000f3d62"
    MS_STATE_DELIVERING: str = "ffbe5466-9fd0-11ee-0a80-0641000f3d64"
    MS_STATE_DELIVERED: str = "ffc02196-9fd0-11ee-0a80-0641000f3d66"
    MS_STATE_CANCELLED: str = "ffc1c72c-9fd0-11ee-0a80-0641000f3d68"
    MS_STATE_CANCELLED_SELLER: str = "f0eb0431-48e1-11ef-0a80-038300102a70"
    MS_STATE_NOT_ACCEPTED_SC: str = "be03b452-5c51-11ef-0a80-1859001ada30"

    # MS state for Demand
    MS_DEMAND_STATE: str = "cd6b3552-44e4-11f0-0a80-19f8002318f7"

    # pricing
    MS_SALE_PRICE_TYPE_ID: str = "12d73934-8b6c-11e9-9109-f8fc00176e29"  # "Цена продажи"

    # sync window & polling
    SYNC_DAYS: int = 20
    SYNC_NOT_BEFORE_UTC: datetime = datetime(2026, 2, 18, 0, 0, 0, tzinfo=timezone.utc)
    POLL_SECONDS: int = 40

    # absolute state path (../data/state.json from src/)
    STATE_PATH: str = str((Path(__file__).resolve().parent.parent / "data" / "state.json").resolve())
