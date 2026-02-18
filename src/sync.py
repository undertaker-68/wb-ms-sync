from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from .config import Config
from . import log
from .state import State, remember, forget_forever, forget_active, is_forgotten
from . import wb
from . import ms


def to_unix(dt: datetime) -> int:
    return int(dt.timestamp())


def get_window(cfg: Config) -> Tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    frm = now - timedelta(days=cfg.SYNC_DAYS)
    if frm < cfg.SYNC_NOT_BEFORE_UTC:
        frm = cfg.SYNC_NOT_BEFORE_UTC
    return frm, now


def map_wb_to_ms_state(cfg: Config, supplier: str, wb_status: str) -> Optional[str]:
    # приоритет: отмены/финал
    if wb_status in ("canceled_by_client", "declined_by_client", "defect"):
        return cfg.MS_STATE_CANCELLED
    if supplier == "cancel":
        return cfg.MS_STATE_CANCELLED_SELLER
    if wb_status == "canceled":
        return cfg.MS_STATE_CANCELLED_SELLER
    if wb_status == "sold":
        return cfg.MS_STATE_DELIVERED

    # процесс
    if supplier == "new" and wb_status == "waiting":
        return cfg.MS_STATE_NEW
    if supplier == "confirm" and wb_status == "waiting":
        return cfg.MS_STATE_AWAIT_ASSEMBLY
    if supplier == "complete" and wb_status == "waiting":
        return cfg.MS_STATE_AWAIT_SHIPMENT
    if supplier == "complete" and wb_status == "sorted":
        return cfg.MS_STATE_SHIPPED
    if supplier == "complete" and wb_status == "ready_for_pickup":
        return cfg.MS_STATE_DELIVERING

    # "Не принят СЦ" добавим, когда увидим реальный wbStatus
    return None


def expand_article_to_positions(cfg: Config, article: str, qty: float) -> Tuple[bool, str, List[Dict[str, Any]]]:
    """
    Возвращает (ok, err, positions) для CustomerOrder (с reserve).
    Правило: если не найден товар/цена/компонент -> ok=False.
    """
    # 1) bundle?
    b = ms.find_bundle_by_article(cfg.MS_BASE, cfg.MS_TOKEN, article)
    if b:
        comps = ms.get_bundle_components(cfg.MS_BASE, cfg.MS_TOKEN, b["id"])
        positions: List[Dict[str, Any]] = []
        for c in comps:
            href = c["assortment"]["meta"]["href"]
            prod = ms.get_assortment_full(href, cfg.MS_TOKEN)
            price = ms.get_sale_price_value(prod, cfg.MS_SALE_PRICE_TYPE_ID)
            if price is None:
                return False, f"no sale price for component href={href}", []
            q = float(c["quantity"]) * float(qty)
            positions.append(
                {
                    "quantity": q,
                    "price": price,
                    "reserve": q,
                    "assortment": {"meta": {"href": href, "type": "product", "mediaType": "application/json"}},
                }
            )
        return True, "", positions

    # 2) product
    p = ms.find_product_by_article(cfg.MS_BASE, cfg.MS_TOKEN, article)
    if not p:
        return False, f"not found article={article}", []
    price = ms.get_sale_price_value(p, cfg.MS_SALE_PRICE_TYPE_ID)
    if price is None:
        return False, f"no sale price for article={article}", []
    href = p["meta"]["href"]
    q = float(qty)
    return True, "", [
        {
            "quantity": q,
            "price": price,
            "reserve": q,
            "assortment": {"meta": {"href": href, "type": "product", "mediaType": "application/json"}},
        }
    ]


def build_customerorder_body(cfg: Config, wb_id: str, positions: List[Dict[str, Any]]) -> Dict[str, Any]:
    b = cfg.MS_BASE
    return {
        "name": str(wb_id),
        "organization": {
            "meta": {"href": f"{b}/entity/organization/{cfg.MS_ORG_ID}", "type": "organization", "mediaType": "application/json"}
        },
        "agent": {
            "meta": {"href": f"{b}/entity/counterparty/{cfg.MS_AGENT_ID}", "type": "counterparty", "mediaType": "application/json"}
        },
        "salesChannel": {
            "meta": {"href": f"{b}/entity/saleschannel/{cfg.MS_SALESCHANNEL_ID}", "type": "saleschannel", "mediaType": "application/json"}
        },
        "store": {"meta": {"href": f"{b}/entity/store/{cfg.MS_STORE_ID}", "type": "store", "mediaType": "application/json"}},
        "state": {
            "meta": {"href": f"{b}/entity/customerorder/metadata/states/{cfg.MS_STATE_NEW}", "type": "state", "mediaType": "application/json"}
        },
        "applicable": True,
        "positions": positions,
    }


def build_demand_body(cfg: Config, wb_id: str, positions_no_reserve: List[Dict[str, Any]]) -> Dict[str, Any]:
    b = cfg.MS_BASE
    return {
        "name": str(wb_id),
        "organization": {
            "meta": {"href": f"{b}/entity/organization/{cfg.MS_ORG_ID}", "type": "organization", "mediaType": "application/json"}
        },
        "store": {"meta": {"href": f"{b}/entity/store/{cfg.MS_STORE_ID}", "type": "store", "mediaType": "application/json"}},
        "state": {
            "meta": {"href": f"{b}/entity/demand/metadata/states/{cfg.MS_DEMAND_STATE}", "type": "state", "mediaType": "application/json"}
        },
        "applicable": True,
        "positions": positions_no_reserve,
    }


def set_customerorder_state(cfg: Config, customerorder_href: str, state_id: str) -> None:
    body = {
        "state": {
            "meta": {
                "href": f"{cfg.MS_BASE}/entity/customerorder/metadata/states/{state_id}",
                "type": "state",
                "mediaType": "application/json",
            }
        }
    }
    ms.ms_put_json(customerorder_href, cfg.MS_TOKEN, body)


def create_customerorder(cfg: Config, wb_id: str, positions: List[Dict[str, Any]]) -> Dict[str, Any]:
    url = f"{cfg.MS_BASE}/entity/customerorder"
    return ms.ms_post_json(url, cfg.MS_TOKEN, build_customerorder_body(cfg, wb_id, positions))


def create_demand(cfg: Config, wb_id: str, positions_no_reserve: List[Dict[str, Any]]) -> None:
    url = f"{cfg.MS_BASE}/entity/demand"
    ms.ms_post_json(url, cfg.MS_TOKEN, build_demand_body(cfg, wb_id, positions_no_reserve))


def is_terminal(supplier: str, wb_status: str) -> bool:
    return (wb_status in ("sold", "canceled_by_client", "declined_by_client", "defect", "canceled")) or (supplier == "cancel")


def sync_once(cfg: Config, state: State) -> None:
    frm, to = get_window(cfg)
    date_from = to_unix(frm)
    date_to = to_unix(to)

    # 1) WB orders window
    orders = wb.get_orders(cfg.WB_TOKEN, date_from, date_to)

    # 2) Create CustomerOrder (только если не active и не forgotten, и если не существует в МС по name)
    for o in orders:
        wb_id = str(o["id"])

        if is_forgotten(state, wb_id):
            continue
        if wb_id in state.active:
            continue

        # если CustomerOrder уже есть -> забываем навсегда
        existing = ms.find_one_by_name(cfg.MS_BASE, cfg.MS_TOKEN, "customerorder", wb_id)
        if existing:
            forget_forever(state, wb_id)
            continue

        # WB list endpoint: article есть, qty обычно нет -> считаем qty=1
        article = str(o.get("article", "")).strip()
        if not article:
            log.warn(f"WB {wb_id} has no article -> skip & forget forever")
            forget_forever(state, wb_id)
            continue

        ok, err, positions = expand_article_to_positions(cfg, article, 1.0)
        if not ok:
            log.warn(f"WB {wb_id} skip (positions): {err} -> forget forever")
            forget_forever(state, wb_id)
            continue

        try:
            co = create_customerorder(cfg, wb_id, positions)
            remember(state, wb_id, ms_order_id=co["id"], ms_order_href=co["meta"]["href"])
            log.info(f"Created CustomerOrder name={wb_id}")
        except Exception as e:
            log.error(f"Create CustomerOrder failed wbId={wb_id}: {e} -> forget forever")
            forget_forever(state, wb_id)

    # 3) Track statuses only for active
    active_ids = list(state.active.keys())
    if not active_ids:
        return

    ids_int = [int(x) for x in active_ids if x.isdigit()]
    chunk = 100
    for i in range(0, len(ids_int), chunk):
        part = ids_int[i : i + chunk]
        statuses = wb.get_statuses(cfg.WB_TOKEN, part)

        for s in statuses:
            wb_id = str(s["id"])
            mem = state.active.get(wb_id)
            if not mem:
                continue

            co_href = mem["msOrderHref"]
            co_id = mem["msOrderId"]

            supplier = s.get("supplierStatus") or ""
            wb_status = s.get("wbStatus") or ""

            # terminal => обновляем состояние (если можем) и забываем навсегда
            if is_terminal(supplier, wb_status):
                ms_state = map_wb_to_ms_state(cfg, supplier, wb_status)
                try:
                    if ms_state:
                        set_customerorder_state(cfg, co_href, ms_state)
                except Exception as e:
                    # если МС временно недоступен — НЕ забываем, попробуем в след. цикл
                    log.warn(f"Terminal status but MS update failed wbId={wb_id}: {e}")
                    continue

                forget_forever(state, wb_id)
                continue

            # trigger demand: complete+sorted
            if supplier == "complete" and wb_status == "sorted":
                try:
                    # антидубль: Demand по name
                    d = ms.find_one_by_name(cfg.MS_BASE, cfg.MS_TOKEN, "demand", wb_id)
                    if d:
                        forget_forever(state, wb_id)
                        continue

                    # антидубль: связанный demand у заказа
                    if ms.has_linked_demand(cfg.MS_BASE, cfg.MS_TOKEN, co_id):
                        forget_forever(state, wb_id)
                        continue

                    # проставляем "Отгружено"
                    set_customerorder_state(cfg, co_href, cfg.MS_STATE_SHIPPED)

                    # позиции Demand: из позиций заказа, без reserve
                    rows = ms.get_positions(co_href, cfg.MS_TOKEN)
                    dpos: List[Dict[str, Any]] = []
                    for p in rows:
                        dpos.append(
                            {
                                "quantity": float(p["quantity"]),
                                "price": float(p["price"]),
                                "assortment": {"meta": p["assortment"]["meta"]},
                            }
                        )

                    create_demand(cfg, wb_id, dpos)
                    log.info(f"Created Demand name={wb_id}")
                except Exception as e:
                    log.error(f"Demand flow failed wbId={wb_id}: {e} -> forget forever")
                finally:
                    # по ТЗ: после попытки Demand — забываем навсегда (без ретраев)
                    forget_forever(state, wb_id)
                continue

            # промежуточные: обновляем состояние (если маппится) и остаёмся в памяти
            ms_state = map_wb_to_ms_state(cfg, supplier, wb_status)
            if ms_state:
                try:
                    set_customerorder_state(cfg, co_href, ms_state)
                except Exception as e:
                    # временные ошибки МС не валят цикл
                    log.warn(f"MS state update failed wbId={wb_id}: {e}")
