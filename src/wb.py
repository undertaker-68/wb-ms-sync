from __future__ import annotations
import requests
from typing import Any, Dict, List

WB_BASE = "https://marketplace-api.wildberries.ru/api/v3"

def _headers(token: str) -> Dict[str, str]:
    return {"Authorization": token, "Accept": "application/json"}

def get_orders(token: str, date_from: int, date_to: int, limit: int = 1000) -> List[Dict[str, Any]]:
    orders: List[Dict[str, Any]] = []
    next_val = 0
    while True:
        url = f"{WB_BASE}/orders"
        params = {"limit": limit, "next": next_val, "dateFrom": date_from, "dateTo": date_to}
        r = requests.get(url, headers=_headers(token), params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        batch = data.get("orders") or []
        orders.extend(batch)
        if len(batch) < limit:
            break
        next_val = data.get("next", 0)
    return orders

def get_statuses(token: str, order_ids: List[int]) -> List[Dict[str, Any]]:
    if not order_ids:
        return []
    url = f"{WB_BASE}/orders/status"
    r = requests.post(url, headers=_headers(token), json={"orders": order_ids}, timeout=30)
    r.raise_for_status()
    data = r.json()
    return data.get("orders") or []
