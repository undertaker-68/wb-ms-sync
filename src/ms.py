from __future__ import annotations

import time
import requests
from typing import Any, Dict, List, Optional

from . import log


class MsHttpError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None, body: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


def ms_headers(token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json;charset=utf-8",
        # content-type выставляем requests'ом автоматически при json=...
    }


def _raise_for_status_with_body(r: requests.Response, context: str) -> None:
    if 200 <= r.status_code < 300:
        return
    body = ""
    try:
        body = r.text or ""
    except Exception:
        body = ""
    msg = f"MS {context} failed: HTTP {r.status_code}"
    if body:
        msg += f" body={body[:2000]}"
    raise MsHttpError(msg, status_code=r.status_code, body=body)


def request_ms(
    method: str,
    url: str,
    token: str,
    *,
    json_body=None,
    timeout: int = 40,
    max_tries: int = 6,
) -> requests.Response:
    h = ms_headers(token)

    last_exc: Exception | None = None
    for attempt in range(1, max_tries + 1):
        try:
            r = requests.request(method, url, headers=h, json=json_body, timeout=timeout)

            # 429 retry
            if r.status_code == 429:
                retry_after = r.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    sleep_s = int(retry_after)
                else:
                    sleep_s = min(2 ** (attempt - 1), 32)
                log.warn(f"MS 429 for {method} {url} -> sleep {sleep_s}s (attempt {attempt}/{max_tries})")
                time.sleep(sleep_s)
                continue

            return r
        except requests.RequestException as e:
            last_exc = e
            if attempt == max_tries:
                break
            sleep_s = min(2 ** (attempt - 1), 16)
            log.warn(f"MS network error for {method} {url}: {e} -> sleep {sleep_s}s (attempt {attempt}/{max_tries})")
            time.sleep(sleep_s)

    raise MsHttpError(f"MS request failed after retries: {method} {url}. Last error: {last_exc}")


def ms_get_json(url: str, token: str) -> Dict[str, Any]:
    r = request_ms("GET", url, token)
    _raise_for_status_with_body(r, f"GET {url}")
    try:
        return r.json()
    except Exception as e:
        raise MsHttpError(f"MS GET {url} invalid json: {e}", status_code=r.status_code, body=r.text)


def ms_post_json(url: str, token: str, body: Dict[str, Any]) -> Dict[str, Any]:
    r = request_ms("POST", url, token, json_body=body)
    _raise_for_status_with_body(r, f"POST {url}")
    try:
        return r.json()
    except Exception as e:
        raise MsHttpError(f"MS POST {url} invalid json: {e}", status_code=r.status_code, body=r.text)


def ms_put_json(url: str, token: str, body: Dict[str, Any]) -> Dict[str, Any]:
    r = request_ms("PUT", url, token, json_body=body)
    _raise_for_status_with_body(r, f"PUT {url}")
    try:
        return r.json()
    except Exception as e:
        raise MsHttpError(f"MS PUT {url} invalid json: {e}", status_code=r.status_code, body=r.text)


def find_one_by_name(ms_base: str, token: str, entity: str, name: str) -> Optional[Dict[str, Any]]:
    url = f"{ms_base}/entity/{entity}?filter=name={name}&limit=1"
    data = ms_get_json(url, token)
    rows = data.get("rows") or []
    return rows[0] if rows else None


def find_product_by_article(ms_base: str, token: str, article: str) -> Optional[Dict[str, Any]]:
    url = f"{ms_base}/entity/product?filter=article={article}&limit=1"
    data = ms_get_json(url, token)
    rows = data.get("rows") or []
    return rows[0] if rows else None


def find_bundle_by_article(ms_base: str, token: str, article: str) -> Optional[Dict[str, Any]]:
    url = f"{ms_base}/entity/bundle?filter=article={article}&limit=1"
    data = ms_get_json(url, token)
    rows = data.get("rows") or []
    return rows[0] if rows else None


def get_bundle_components(ms_base: str, token: str, bundle_id: str) -> List[Dict[str, Any]]:
    url = f"{ms_base}/entity/bundle/{bundle_id}/components?limit=1000&offset=0"
    data = ms_get_json(url, token)
    return data.get("rows") or []


def get_sale_price_value(obj: Dict[str, Any], sale_price_type_id: str) -> Optional[float]:
    for p in (obj.get("salePrices") or []):
        pt = p.get("priceType") or {}
        if pt.get("id") == sale_price_type_id:
            return float(p.get("value"))
    return None


def get_assortment_full(href: str, token: str) -> Dict[str, Any]:
    return ms_get_json(href, token)


def get_positions(customerorder_href: str, token: str) -> List[Dict[str, Any]]:
    url = f"{customerorder_href}/positions?limit=1000&offset=0"
    data = ms_get_json(url, token)
    return data.get("rows") or []


def has_linked_demand(ms_base: str, token: str, customerorder_id: str) -> bool:
    """
    Требование: "если у customerorder есть связанные meta demand — второй demand не создаем".
    В МС в разных аккаунтах поле связей может выглядеть по-разному.
    Стратегия:
      1) customerorder/{id}?expand=demands — если вернуло demands[] и оно не пустое -> True
      2) fallback: customerorder/{id} без expand — ищем поля demands/related/relatedDocuments
      3) fallback: пробуем отфильтровать demand по customerOrder (если API позволяет), иначе False.
    """
    # 1) expand=demands
    try:
        url = f"{ms_base}/entity/customerorder/{customerorder_id}?expand=demands"
        data = ms_get_json(url, token)
        demands = data.get("demands")
        if isinstance(demands, list) and len(demands) > 0:
            return True
        # иногда demands приходит как объект с meta/rows
        if isinstance(demands, dict):
            rows = demands.get("rows") or []
            if rows:
                return True
    except Exception as e:
        log.warn(f"has_linked_demand: expand=demands failed: {e}")

    # 2) без expand — ищем возможные поля
    try:
        url = f"{ms_base}/entity/customerorder/{customerorder_id}"
        data = ms_get_json(url, token)

        for key in ("demands", "related", "relatedDocuments"):
            v = data.get(key)
            if isinstance(v, list) and len(v) > 0:
                return True
            if isinstance(v, dict):
                rows = v.get("rows") or []
                if rows:
                    return True

        # иногда связи лежат внутри meta/attributes — оставим проверку на случай
        meta = data.get("meta") or {}
        if isinstance(meta, dict):
            # не универсально, но безопасно
            if "demands" in meta:
                return True
    except Exception as e:
        log.warn(f"has_linked_demand: base customerorder fetch failed: {e}")

    # 3) последний шанс: поиск demand по фильтру customerOrder (в некоторых окружениях это работает)
    # если не работает — вернёт 400, мы проглотим и вернём False.
    try:
        url = f"{ms_base}/entity/demand?filter=customerOrder.id={customerorder_id}&limit=1"
        data = ms_get_json(url, token)
        rows = data.get("rows") or []
        return len(rows) > 0
    except Exception:
        return False
