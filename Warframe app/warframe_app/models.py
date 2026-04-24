from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class AlertItem:
    title: str
    description: str
    severity: str


@dataclass(slots=True)
class ActivityItem:
    name: str
    focus: str
    note: str


@dataclass(slots=True)
class MarketOrder:
    item_name: str
    order_type: str
    platinum: int
    quantity: int
    platform: str


@dataclass(slots=True)
class RelicDrop:
    relic_name: str
    rarity: str
    reward: str
    chance: str


@dataclass(slots=True)
class FeatureModule:
    phase: str
    area: str
    name: str
    summary: str
    dependencies: str
    release: str


@dataclass(slots=True)
class IntegrationNeed:
    layer: str
    source: str
    access: str
    used_for: str
    priority: str


@dataclass(slots=True)
class MissingPiece:
    area: str
    impact: str
    needed_from_user: str
    notes: str


@dataclass(slots=True)
class NextStep:
    step: str
    outcome: str


@dataclass(slots=True)
class LiveCycle:
    name: str
    state: str
    remaining: str
    expires_at: str


@dataclass(slots=True)
class FissureMission:
    tier: str
    mission_type: str
    node: str
    enemy: str
    eta: str
    is_steel_path: bool


@dataclass(slots=True)
class ActiveEvent:
    name: str
    node: str
    eta: str
    rewards: str


@dataclass(slots=True)
class VendorStatus:
    name: str
    location: str
    eta: str
    inventory_preview: str


@dataclass(slots=True)
class WorldstateSnapshot:
    fetched_at: str
    status: str
    cycles: list[LiveCycle]
    fissures: list[FissureMission]
    events: list[ActiveEvent]
    vendors: list[VendorStatus]


@dataclass(slots=True)
class VosforSourceEntry:
    source: str
    item_name: str
    chance: str
    avg_price_rank0: str
    avg_price_maxed: str
    expected_rank0: str
    expected_maxed: str
    unit_price_maxed: str


@dataclass(slots=True)
class VosforTopEntry:
    item_name: str
    vosfor_amount: str
    platinum: str
    vosfor_per_plat: str


@dataclass(slots=True)
class BaroDeal:
    item_name: str
    ducats: str
    platinum: str
    profit: str


@dataclass(slots=True)
class VosforSnapshot:
    imported_at: str
    workbook_path: str
    gambling_entries: list[VosforSourceEntry]
    top_entries: list[VosforTopEntry]
    baro_deals: list[BaroDeal]


@dataclass(slots=True)
class DashboardSnapshot:
    last_updated: str
    alerts: list[AlertItem]
    activities: list[ActivityItem]
    tracked_items: list[str]
    tracked_relics: list[str]
    feature_modules: list[FeatureModule]
    integrations: list[IntegrationNeed]
    missing_pieces: list[MissingPiece]
    live_ops: WorldstateSnapshot
    vosfor: VosforSnapshot


@dataclass(slots=True)
class MarketCatalogItem:
    item_name: str
    url_name: str
    thumb_url: str = ""
    icon_url: str = ""
    max_rank: int = 0
    is_set: bool = False


@dataclass(slots=True)
class MarketMetric:
    label: str
    value: str
    detail: str


@dataclass(slots=True)
class MarketTradeStat:
    captured_at: str
    rank: str
    avg_price: str
    median_price: str
    volume: str
    price_range: str
    moving_average: str


@dataclass(slots=True)
class MarketLiveOrder:
    seller_name: str
    price: str
    quantity: str
    rank: str
    updated_at: str
    reputation: str
    whisper_text: str
    platform: str
    crossplay: str
    order_id: str


@dataclass(slots=True)
class MarketSnapshot:
    item_name: str
    url_name: str
    fetched_at: str
    status: str
    image_url: str
    thumb_url: str
    max_rank: int
    is_set: bool
    best_price: str
    ingame_sellers: str
    metrics: list[MarketMetric]
    orders: list[MarketLiveOrder]
    recent_trades: list[MarketTradeStat]
    trend_trades: list[MarketTradeStat]


@dataclass(slots=True)
class RelicSnapshot:
    relic_name: str
    drops: list[RelicDrop]
