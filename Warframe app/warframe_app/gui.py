from __future__ import annotations

import io
import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from PIL import Image, ImageTk

from warframe_app.models import (
    DashboardSnapshot,
    MarketLiveOrder,
    MarketSnapshot,
    VosforSnapshot,
    WorldstateSnapshot,
)
from warframe_app.services import WarframeDataService


class WarframeAssistantApp(tk.Tk):
    def __init__(self, service: WarframeDataService) -> None:
        super().__init__()
        self.service = service
        self.title("Warframe Companion")
        self.geometry("1460x960")
        self.minsize(1220, 820)
        self.configure(bg="#11161d")

        self.market_query = tk.StringVar(value="Arcane Energize")
        self.relic_query = tk.StringVar(value="Axi A18")
        self.market_status = tk.StringVar(value="Market wird vorbereitet...")
        self.relic_status = tk.StringVar(value="Relic-Drops bereit.")
        self.worldstate_status = tk.StringVar(value="Worldstate wird geladen...")
        self.vosfor_status = tk.StringVar(value="Vosfor-Sheet wird geladen...")
        self.market_auto_refresh = tk.BooleanVar(value=True)
        self.market_refresh_seconds = tk.IntVar(value=60)

        self.market_row_map: dict[str, MarketLiveOrder] = {}
        self.current_market_snapshot: MarketSnapshot | None = None
        self.market_image_ref: ImageTk.PhotoImage | None = None
        self.market_refresh_after_id: str | None = None
        self.market_request_id = 0
        self.latest_market_request_id = 0
        self.market_task_queue: queue.Queue[tuple[int, str, bool] | None] = queue.Queue()
        self.market_result_queue: queue.Queue[tuple[str, int, object, bytes | None]] = queue.Queue()
        self.market_worker = threading.Thread(target=self._market_worker_loop, daemon=True)
        self.market_worker.start()

        self._configure_styles()
        self._build_layout()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(150, self.refresh_all_views)
        self.after(200, self._poll_market_results)

    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure(".", background="#11161d", foreground="#eef4ff")
        style.configure("TFrame", background="#11161d")
        style.configure("TLabel", background="#11161d", foreground="#eef4ff")
        style.configure("TNotebook", background="#11161d", borderwidth=0)
        style.configure("TNotebook.Tab", padding=(18, 10), background="#1b2430", foreground="#eef4ff")
        style.map("TNotebook.Tab", background=[("selected", "#2a3b52")])
        style.configure("Card.TLabelframe", background="#18212d", foreground="#eef4ff")
        style.configure("Card.TLabelframe.Label", background="#18212d", foreground="#eef4ff")
        style.configure("Treeview", background="#1a2230", fieldbackground="#1a2230", foreground="#eef4ff", rowheight=28)
        style.configure("Treeview.Heading", background="#27364a", foreground="#eef4ff")
        style.map("Treeview", background=[("selected", "#34547a")])
        style.configure("Primary.TButton", background="#e28f2d", foreground="#10151b", padding=(14, 8))
        style.map("Primary.TButton", background=[("active", "#f3a33c")])
        style.configure("Secondary.TButton", background="#2a3b52", foreground="#eef4ff", padding=(12, 8))
        style.map("Secondary.TButton", background=[("active", "#34547a")])

    def _build_layout(self) -> None:
        shell = ttk.Frame(self, padding=18)
        shell.pack(fill="both", expand=True)

        self._build_header(shell)

        notebook = ttk.Notebook(shell)
        notebook.pack(fill="both", expand=True, pady=(12, 0))

        self.dashboard_tab = ttk.Frame(notebook, padding=16)
        self.live_ops_tab = ttk.Frame(notebook, padding=16)
        self.vosfor_tab = ttk.Frame(notebook, padding=16)
        self.market_tab = ttk.Frame(notebook, padding=16)
        self.relic_tab = ttk.Frame(notebook, padding=16)
        self.roadmap_tab = ttk.Frame(notebook, padding=16)
        self.requirements_tab = ttk.Frame(notebook, padding=16)

        notebook.add(self.dashboard_tab, text="Dashboard")
        notebook.add(self.live_ops_tab, text="Live Ops")
        notebook.add(self.vosfor_tab, text="Vosfor")
        notebook.add(self.market_tab, text="Market")
        notebook.add(self.relic_tab, text="Relics")
        notebook.add(self.roadmap_tab, text="Roadmap")
        notebook.add(self.requirements_tab, text="Requirements")

        self._build_dashboard_tab()
        self._build_live_ops_tab()
        self._build_vosfor_tab()
        self._build_market_tab()
        self._build_relic_tab()
        self._build_roadmap_tab()
        self._build_requirements_tab()

    def _build_header(self, parent: ttk.Frame) -> None:
        header = ttk.Frame(parent)
        header.pack(fill="x")

        title_col = ttk.Frame(header)
        title_col.pack(side="left", fill="x", expand=True)

        tk.Label(
            title_col,
            text="Warframe Companion",
            font=("Segoe UI Semibold", 24),
            bg="#11161d",
            fg="#f7fbff",
        ).pack(anchor="w")
        tk.Label(
            title_col,
            text="Live Worldstate, Vosfor und ein echter ingame-only Market-Flow mit Whisper-Texten.",
            font=("Segoe UI", 11),
            bg="#11161d",
            fg="#9eb2ca",
        ).pack(anchor="w", pady=(4, 0))

        ttk.Button(
            header,
            text="Daten neu laden",
            command=self.refresh_all_views,
            style="Secondary.TButton",
        ).pack(side="right")

    def _build_dashboard_tab(self) -> None:
        top = ttk.Frame(self.dashboard_tab)
        top.pack(fill="x")
        for index in range(4):
            top.columnconfigure(index, weight=1)

        self.summary_labels: dict[str, tk.Label] = {}
        for column, (key, title) in enumerate(
            [
                ("fissures", "Active Fissures"),
                ("events", "Events"),
                ("vendors", "Vendors"),
                ("vosfor", "Vosfor Rows"),
            ]
        ):
            card = ttk.LabelFrame(top, text=title, style="Card.TLabelframe", padding=16)
            card.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 10, 0))
            label = tk.Label(
                card,
                text="0",
                font=("Segoe UI Semibold", 28),
                bg="#18212d",
                fg="#f7fbff",
            )
            label.pack(anchor="w")
            self.summary_labels[key] = label

        bottom = ttk.Frame(self.dashboard_tab)
        bottom.pack(fill="both", expand=True, pady=(16, 0))
        for index in range(2):
            bottom.columnconfigure(index, weight=1)
        bottom.rowconfigure(0, weight=1)

        alerts_frame = ttk.LabelFrame(bottom, text="Current Priorities", style="Card.TLabelframe", padding=12)
        alerts_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.alert_tree = ttk.Treeview(
            alerts_frame,
            columns=("severity", "title", "description"),
            show="headings",
            height=10,
        )
        for column, text, width in (
            ("severity", "Priority", 110),
            ("title", "Bereich", 220),
            ("description", "Warum jetzt", 430),
        ):
            self.alert_tree.heading(column, text=text)
            self.alert_tree.column(column, width=width, anchor="w")
        self.alert_tree.pack(fill="both", expand=True)

        activity_frame = ttk.LabelFrame(bottom, text="Delivery Order", style="Card.TLabelframe", padding=12)
        activity_frame.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        self.activity_tree = ttk.Treeview(
            activity_frame,
            columns=("name", "focus", "note"),
            show="headings",
            height=10,
        )
        for column, text, width in (
            ("name", "Phase", 210),
            ("focus", "Fokus", 180),
            ("note", "Ergebnis", 400),
        ):
            self.activity_tree.heading(column, text=text)
            self.activity_tree.column(column, width=width, anchor="w")
        self.activity_tree.pack(fill="both", expand=True)

        self.dashboard_meta = tk.Label(
            self.dashboard_tab,
            text="Noch nicht synchronisiert.",
            font=("Segoe UI", 10),
            bg="#11161d",
            fg="#9eb2ca",
        )
        self.dashboard_meta.pack(anchor="w", pady=(12, 0))

    def _build_live_ops_tab(self) -> None:
        tk.Label(
            self.live_ops_tab,
            textvariable=self.worldstate_status,
            font=("Segoe UI", 10),
            bg="#11161d",
            fg="#9eb2ca",
        ).pack(anchor="w")

        top = ttk.Frame(self.live_ops_tab)
        top.pack(fill="both", expand=True, pady=(12, 0))
        for index in range(2):
            top.columnconfigure(index, weight=1)
        top.rowconfigure(0, weight=1)

        cycles_frame = ttk.LabelFrame(top, text="Cycles", style="Card.TLabelframe", padding=12)
        cycles_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.cycles_tree = ttk.Treeview(
            cycles_frame,
            columns=("name", "state", "remaining", "expires"),
            show="headings",
            height=8,
        )
        for column, text, width in (
            ("name", "Zone", 160),
            ("state", "State", 140),
            ("remaining", "Remaining", 150),
            ("expires", "Expires", 170),
        ):
            self.cycles_tree.heading(column, text=text)
            self.cycles_tree.column(column, width=width, anchor="w")
        self.cycles_tree.pack(fill="both", expand=True)

        vendors_frame = ttk.LabelFrame(top, text="Vendors", style="Card.TLabelframe", padding=12)
        vendors_frame.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        self.vendor_tree = ttk.Treeview(
            vendors_frame,
            columns=("name", "location", "eta", "preview"),
            show="headings",
            height=8,
        )
        for column, text, width in (
            ("name", "Vendor", 130),
            ("location", "Location", 180),
            ("eta", "Status", 180),
            ("preview", "Inventory Preview", 360),
        ):
            self.vendor_tree.heading(column, text=text)
            self.vendor_tree.column(column, width=width, anchor="w")
        self.vendor_tree.pack(fill="both", expand=True)

        bottom = ttk.Frame(self.live_ops_tab)
        bottom.pack(fill="both", expand=True, pady=(16, 0))
        for index in range(2):
            bottom.columnconfigure(index, weight=1)
        bottom.rowconfigure(0, weight=1)

        fissures_frame = ttk.LabelFrame(bottom, text="Fissures", style="Card.TLabelframe", padding=12)
        fissures_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.fissure_tree = ttk.Treeview(
            fissures_frame,
            columns=("tier", "mission", "node", "enemy", "eta", "sp"),
            show="headings",
            height=12,
        )
        for column, text, width in (
            ("tier", "Tier", 90),
            ("mission", "Mission", 160),
            ("node", "Node", 180),
            ("enemy", "Enemy", 120),
            ("eta", "ETA", 100),
            ("sp", "SP", 70),
        ):
            self.fissure_tree.heading(column, text=text)
            self.fissure_tree.column(column, width=width, anchor="w")
        self.fissure_tree.pack(fill="both", expand=True)

        events_frame = ttk.LabelFrame(bottom, text="Events", style="Card.TLabelframe", padding=12)
        events_frame.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        self.events_tree = ttk.Treeview(
            events_frame,
            columns=("name", "node", "eta", "rewards"),
            show="headings",
            height=12,
        )
        for column, text, width in (
            ("name", "Event", 220),
            ("node", "Node", 180),
            ("eta", "ETA", 110),
            ("rewards", "Rewards", 330),
        ):
            self.events_tree.heading(column, text=text)
            self.events_tree.column(column, width=width, anchor="w")
        self.events_tree.pack(fill="both", expand=True)

    def _build_vosfor_tab(self) -> None:
        tk.Label(
            self.vosfor_tab,
            textvariable=self.vosfor_status,
            font=("Segoe UI", 10),
            bg="#11161d",
            fg="#9eb2ca",
        ).pack(anchor="w")

        top = ttk.Frame(self.vosfor_tab)
        top.pack(fill="both", expand=True, pady=(12, 0))
        for index in range(2):
            top.columnconfigure(index, weight=1)
        top.rowconfigure(0, weight=1)

        top_entries_frame = ttk.LabelFrame(top, text="Top Vosfor per Plat", style="Card.TLabelframe", padding=12)
        top_entries_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.top_vosfor_tree = ttk.Treeview(
            top_entries_frame,
            columns=("item", "vosfor", "plat", "ratio"),
            show="headings",
            height=8,
        )
        for column, text, width in (
            ("item", "Arcane", 220),
            ("vosfor", "Vosfor", 120),
            ("plat", "Plat", 120),
            ("ratio", "Vosfor/Plat", 120),
        ):
            self.top_vosfor_tree.heading(column, text=text)
            self.top_vosfor_tree.column(column, width=width, anchor="w")
        self.top_vosfor_tree.pack(fill="both", expand=True)

        baro_frame = ttk.LabelFrame(top, text="Baro Profit", style="Card.TLabelframe", padding=12)
        baro_frame.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        self.baro_tree = ttk.Treeview(
            baro_frame,
            columns=("item", "ducats", "plat", "profit"),
            show="headings",
            height=8,
        )
        for column, text, width in (
            ("item", "Item", 240),
            ("ducats", "Ducats", 90),
            ("plat", "Plat", 90),
            ("profit", "Profit", 100),
        ):
            self.baro_tree.heading(column, text=text)
            self.baro_tree.column(column, width=width, anchor="w")
        self.baro_tree.pack(fill="both", expand=True)

        bottom = ttk.Frame(self.vosfor_tab)
        bottom.pack(fill="both", expand=True, pady=(16, 0))
        bottom.columnconfigure(0, weight=1)
        bottom.rowconfigure(0, weight=1)

        gambling_frame = ttk.LabelFrame(bottom, text="Vosfor Gambling Breakdown", style="Card.TLabelframe", padding=12)
        gambling_frame.grid(row=0, column=0, sticky="nsew")
        self.gambling_tree = ttk.Treeview(
            gambling_frame,
            columns=("source", "item", "chance", "rank0", "maxed", "ev0", "evmax", "unitmax"),
            show="headings",
            height=14,
        )
        for column, text, width in (
            ("source", "Source", 130),
            ("item", "Arcane", 220),
            ("chance", "Chance", 90),
            ("rank0", "Rank 0", 90),
            ("maxed", "Maxed", 90),
            ("ev0", "EV Rank 0", 100),
            ("evmax", "EV Maxed", 100),
            ("unitmax", "Unit Max", 90),
        ):
            self.gambling_tree.heading(column, text=text)
            self.gambling_tree.column(column, width=width, anchor="w")
        self.gambling_tree.pack(fill="both", expand=True)

    def _build_market_tab(self) -> None:
        search_bar = ttk.Frame(self.market_tab)
        search_bar.pack(fill="x")

        tk.Label(
            search_bar,
            text="Item oder Set",
            font=("Segoe UI", 11),
            bg="#11161d",
            fg="#eef4ff",
        ).pack(side="left")
        ttk.Entry(search_bar, textvariable=self.market_query, width=40).pack(side="left", padx=10)
        ttk.Button(
            search_bar,
            text="Live laden",
            command=lambda: self.load_market_search(force_refresh=True),
            style="Primary.TButton",
        ).pack(side="left")

        ttk.Checkbutton(
            search_bar,
            text="Auto-Refresh",
            variable=self.market_auto_refresh,
            command=self._reschedule_market_refresh,
        ).pack(side="left", padx=(16, 8))

        tk.Label(
            search_bar,
            text="Sekunden",
            font=("Segoe UI", 10),
            bg="#11161d",
            fg="#eef4ff",
        ).pack(side="left")
        ttk.Spinbox(
            search_bar,
            from_=30,
            to=600,
            increment=15,
            textvariable=self.market_refresh_seconds,
            width=8,
            command=self._reschedule_market_refresh,
        ).pack(side="left", padx=(8, 0))

        quick_bar = ttk.Frame(self.market_tab)
        quick_bar.pack(fill="x", pady=(12, 12))
        tk.Label(
            quick_bar,
            text="Quick Picks",
            font=("Segoe UI", 10),
            bg="#11161d",
            fg="#eef4ff",
        ).pack(side="left")
        for item_name in self.service.list_market_items():
            ttk.Button(
                quick_bar,
                text=item_name,
                style="Secondary.TButton",
                command=lambda value=item_name: self._set_market_query(value),
            ).pack(side="left", padx=(8, 0))

        summary = ttk.Frame(self.market_tab)
        summary.pack(fill="x", pady=(0, 12))
        summary.columnconfigure(1, weight=1)

        image_card = ttk.LabelFrame(summary, text="Item", style="Card.TLabelframe", padding=12)
        image_card.grid(row=0, column=0, sticky="nsw", padx=(0, 12))
        self.market_image_label = tk.Label(
            image_card,
            text="Kein Bild",
            width=14,
            height=7,
            bg="#18212d",
            fg="#9eb2ca",
        )
        self.market_image_label.pack()

        info_card = ttk.LabelFrame(summary, text="Live Summary", style="Card.TLabelframe", padding=16)
        info_card.grid(row=0, column=1, sticky="nsew")
        self.market_summary_labels: dict[str, tk.Label] = {}
        for key, title in (
            ("item", "Item"),
            ("best_price", "Best Ingame Price"),
            ("ingame_sellers", "Ingame Sellers"),
            ("snapshot", "Snapshot"),
        ):
            row = ttk.Frame(info_card)
            row.pack(fill="x", pady=2)
            tk.Label(
                row,
                text=f"{title}:",
                font=("Segoe UI Semibold", 10),
                bg="#18212d",
                fg="#f7fbff",
                width=18,
                anchor="w",
            ).pack(side="left")
            value_label = tk.Label(
                row,
                text="-",
                font=("Segoe UI", 10),
                bg="#18212d",
                fg="#dbe7f7",
                anchor="w",
                justify="left",
                wraplength=780,
            )
            value_label.pack(side="left", fill="x", expand=True)
            self.market_summary_labels[key] = value_label

        metrics_frame = ttk.LabelFrame(self.market_tab, text="Market Metrics", style="Card.TLabelframe", padding=12)
        metrics_frame.pack(fill="x", pady=(0, 12))
        self.market_metrics_tree = ttk.Treeview(
            metrics_frame,
            columns=("label", "value", "detail"),
            show="headings",
            height=5,
        )
        for column, text, width in (
            ("label", "Metric", 200),
            ("value", "Value", 160),
            ("detail", "Detail", 760),
        ):
            self.market_metrics_tree.heading(column, text=text)
            self.market_metrics_tree.column(column, width=width, anchor="w")
        self.market_metrics_tree.pack(fill="x", expand=True)

        orders_frame = ttk.LabelFrame(self.market_tab, text="Live Ingame Sell Orders", style="Card.TLabelframe", padding=12)
        orders_frame.pack(fill="both", expand=True)
        self.market_orders_tree = ttk.Treeview(
            orders_frame,
            columns=("seller", "price", "quantity", "rank", "updated", "rep", "platform", "crossplay"),
            show="headings",
            height=11,
        )
        for column, text, width in (
            ("seller", "Seller", 200),
            ("price", "Price", 90),
            ("quantity", "Qty", 70),
            ("rank", "Rank", 120),
            ("updated", "Updated", 150),
            ("rep", "Rep", 70),
            ("platform", "Platform", 90),
            ("crossplay", "Crossplay", 90),
        ):
            self.market_orders_tree.heading(column, text=text)
            self.market_orders_tree.column(column, width=width, anchor="w")
        self.market_orders_tree.pack(fill="both", expand=True)
        self.market_orders_tree.bind("<<TreeviewSelect>>", self._on_market_order_selected)
        self.market_orders_tree.bind("<Double-1>", self._copy_selected_whisper)

        whisper_frame = ttk.LabelFrame(self.market_tab, text="Whisper Preview", style="Card.TLabelframe", padding=12)
        whisper_frame.pack(fill="x", pady=(12, 0))
        whisper_row = ttk.Frame(whisper_frame)
        whisper_row.pack(fill="x")
        self.whisper_text = tk.Text(
            whisper_row,
            height=3,
            wrap="word",
            bg="#1a2230",
            fg="#eef4ff",
            insertbackground="#eef4ff",
            relief="flat",
        )
        self.whisper_text.pack(side="left", fill="x", expand=True)
        ttk.Button(
            whisper_row,
            text="Whisper kopieren",
            command=self._copy_selected_whisper,
            style="Primary.TButton",
        ).pack(side="left", padx=(12, 0))

        stats = ttk.Frame(self.market_tab)
        stats.pack(fill="both", expand=True, pady=(12, 0))
        for index in range(2):
            stats.columnconfigure(index, weight=1)
        stats.rowconfigure(0, weight=1)

        recent_frame = ttk.LabelFrame(stats, text="Closed Trades (48h)", style="Card.TLabelframe", padding=12)
        recent_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.market_recent_tree = ttk.Treeview(
            recent_frame,
            columns=("captured", "rank", "avg", "median", "volume", "range", "moving"),
            show="headings",
            height=8,
        )
        for column, text, width in (
            ("captured", "Captured", 140),
            ("rank", "Rank", 80),
            ("avg", "Avg", 80),
            ("median", "Median", 80),
            ("volume", "Volume", 80),
            ("range", "Range", 140),
            ("moving", "Moving Avg", 100),
        ):
            self.market_recent_tree.heading(column, text=text)
            self.market_recent_tree.column(column, width=width, anchor="w")
        self.market_recent_tree.pack(fill="both", expand=True)

        trend_frame = ttk.LabelFrame(stats, text="Trend (90d)", style="Card.TLabelframe", padding=12)
        trend_frame.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        self.market_trend_tree = ttk.Treeview(
            trend_frame,
            columns=("captured", "rank", "avg", "median", "volume", "range", "moving"),
            show="headings",
            height=8,
        )
        for column, text, width in (
            ("captured", "Captured", 140),
            ("rank", "Rank", 80),
            ("avg", "Avg", 80),
            ("median", "Median", 80),
            ("volume", "Volume", 80),
            ("range", "Range", 140),
            ("moving", "Moving Avg", 100),
        ):
            self.market_trend_tree.heading(column, text=text)
            self.market_trend_tree.column(column, width=width, anchor="w")
        self.market_trend_tree.pack(fill="both", expand=True)

        tk.Label(
            self.market_tab,
            textvariable=self.market_status,
            font=("Segoe UI", 10),
            bg="#11161d",
            fg="#9eb2ca",
        ).pack(anchor="w", pady=(12, 0))

    def _build_relic_tab(self) -> None:
        search_bar = ttk.Frame(self.relic_tab)
        search_bar.pack(fill="x")

        tk.Label(
            search_bar,
            text="Relic",
            font=("Segoe UI", 11),
            bg="#11161d",
            fg="#eef4ff",
        ).pack(side="left")
        relic_combo = ttk.Combobox(
            search_bar,
            textvariable=self.relic_query,
            values=self.service.list_relics(),
            width=24,
            state="normal",
        )
        relic_combo.pack(side="left", padx=10)
        ttk.Button(
            search_bar,
            text="Drops laden",
            command=self.load_relic_search,
            style="Primary.TButton",
        ).pack(side="left")

        helper = ttk.LabelFrame(self.relic_tab, text="Naechster Schritt fuer dieses Modul", style="Card.TLabelframe", padding=16)
        helper.pack(fill="x", pady=(12, 12))
        self._create_text_block(
            helper,
            [
                "Relic Planner soll spaeter Plat- und Ducat-Erwartungswerte aus Marktpreisen und Inventar kombinieren.",
                "Die SQLite-Basis fuer geoeffnete Relics und Run-History ist vorbereitet.",
            ],
        )

        relic_frame = ttk.LabelFrame(self.relic_tab, text="Drop Table", style="Card.TLabelframe", padding=12)
        relic_frame.pack(fill="both", expand=True)
        self.relic_tree = ttk.Treeview(
            relic_frame,
            columns=("rarity", "reward", "chance"),
            show="headings",
            height=14,
        )
        for column, text, width in (
            ("rarity", "Rarity", 140),
            ("reward", "Reward", 360),
            ("chance", "Chance", 120),
        ):
            self.relic_tree.heading(column, text=text)
            self.relic_tree.column(column, width=width, anchor="w")
        self.relic_tree.pack(fill="both", expand=True)

        tk.Label(
            self.relic_tab,
            textvariable=self.relic_status,
            font=("Segoe UI", 10),
            bg="#11161d",
            fg="#9eb2ca",
        ).pack(anchor="w", pady=(12, 0))

    def _build_roadmap_tab(self) -> None:
        intro_frame = ttk.LabelFrame(
            self.roadmap_tab,
            text="Logische Reihenfolge aus deinen Notizen",
            style="Card.TLabelframe",
            padding=16,
        )
        intro_frame.pack(fill="x")
        self._create_text_block(
            intro_frame,
            [
                "Phase 1 sammelt alles, was global und live ist: Timer, Rotationen, Events, Fissures und Vosfor.",
                "Phase 2 setzt auf den Account-Datenkern auf: Foundry, Mastery, Inventory und Materialplanung.",
                "Phase 3 macht daraus intelligente Trading- und Relic-Tools.",
                "Phase 4 ist alles, was mehr Produkt- oder Backend-Aufwand braucht: Overlay, Party, Clan und Sharing.",
            ],
        )

        roadmap_frame = ttk.LabelFrame(
            self.roadmap_tab,
            text="Feature Breakdown",
            style="Card.TLabelframe",
            padding=12,
        )
        roadmap_frame.pack(fill="both", expand=True, pady=(16, 0))
        self.roadmap_tree = ttk.Treeview(
            roadmap_frame,
            columns=("phase", "area", "name", "dependencies", "release"),
            show="headings",
            height=16,
        )
        for column, text, width in (
            ("phase", "Phase", 90),
            ("area", "Area", 180),
            ("name", "Feature", 260),
            ("dependencies", "Abhaengigkeiten", 430),
            ("release", "Release", 130),
        ):
            self.roadmap_tree.heading(column, text=text)
            self.roadmap_tree.column(column, width=width, anchor="w")
        self.roadmap_tree.pack(fill="both", expand=True)

    def _build_requirements_tab(self) -> None:
        top = ttk.Frame(self.requirements_tab)
        top.pack(fill="both", expand=True)
        for index in range(2):
            top.columnconfigure(index, weight=1)
        top.rowconfigure(0, weight=1)

        integrations_frame = ttk.LabelFrame(top, text="APIs / Integrationen", style="Card.TLabelframe", padding=12)
        integrations_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.integrations_tree = ttk.Treeview(
            integrations_frame,
            columns=("layer", "source", "access", "priority"),
            show="headings",
            height=14,
        )
        for column, text, width in (
            ("layer", "Layer", 180),
            ("source", "Quelle", 220),
            ("access", "Access", 320),
            ("priority", "Priority", 170),
        ):
            self.integrations_tree.heading(column, text=text)
            self.integrations_tree.column(column, width=width, anchor="w")
        self.integrations_tree.pack(fill="both", expand=True)

        missing_frame = ttk.LabelFrame(top, text="Was noch fehlt", style="Card.TLabelframe", padding=12)
        missing_frame.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        self.missing_tree = ttk.Treeview(
            missing_frame,
            columns=("area", "impact", "needed", "notes"),
            show="headings",
            height=14,
        )
        for column, text, width in (
            ("area", "Bereich", 150),
            ("impact", "Impact", 260),
            ("needed", "Von dir / Entscheidung", 290),
            ("notes", "Notes", 250),
        ):
            self.missing_tree.heading(column, text=text)
            self.missing_tree.column(column, width=width, anchor="w")
        self.missing_tree.pack(fill="both", expand=True)

        next_frame = ttk.LabelFrame(
            self.requirements_tab,
            text="Naechste konkrete Schritte",
            style="Card.TLabelframe",
            padding=16,
        )
        next_frame.pack(fill="x", pady=(16, 0))
        self.next_steps_container = next_frame

    def refresh_all_views(self) -> None:
        snapshot = self.service.load_dashboard()
        self._populate_dashboard(snapshot)
        self._populate_live_ops(snapshot.live_ops)
        self._populate_vosfor(snapshot.vosfor)
        self.populate_roadmap()
        self.populate_requirements()
        self.load_market_search(force_refresh=True)
        self.load_relic_search()

    def _populate_dashboard(self, snapshot: DashboardSnapshot) -> None:
        self.summary_labels["fissures"].configure(text=str(len(snapshot.live_ops.fissures)))
        self.summary_labels["events"].configure(text=str(len(snapshot.live_ops.events)))
        self.summary_labels["vendors"].configure(text=str(len(snapshot.live_ops.vendors)))
        self.summary_labels["vosfor"].configure(text=str(len(snapshot.vosfor.gambling_entries)))

        self._replace_tree_rows(
            self.alert_tree,
            [(alert.severity.upper(), alert.title, alert.description) for alert in snapshot.alerts],
        )
        self._replace_tree_rows(
            self.activity_tree,
            [(activity.name, activity.focus, activity.note) for activity in snapshot.activities],
        )
        self.dashboard_meta.configure(
            text=(
                f"Zuletzt aktualisiert: {snapshot.last_updated} | "
                f"SQLite: {self.service.storage.database_path}"
            )
        )

    def _populate_live_ops(self, snapshot: WorldstateSnapshot) -> None:
        self.worldstate_status.set(f"{snapshot.status} | Snapshot: {snapshot.fetched_at}")
        self._replace_tree_rows(
            self.cycles_tree,
            [(cycle.name, cycle.state, cycle.remaining, cycle.expires_at) for cycle in snapshot.cycles],
        )
        self._replace_tree_rows(
            self.vendor_tree,
            [(vendor.name, vendor.location, vendor.eta, vendor.inventory_preview) for vendor in snapshot.vendors],
        )
        self._replace_tree_rows(
            self.fissure_tree,
            [
                (
                    fissure.tier,
                    fissure.mission_type,
                    fissure.node,
                    fissure.enemy,
                    fissure.eta,
                    "Yes" if fissure.is_steel_path else "-",
                )
                for fissure in snapshot.fissures
            ],
        )
        self._replace_tree_rows(
            self.events_tree,
            [(event.name, event.node, event.eta, event.rewards) for event in snapshot.events],
        )

    def _populate_vosfor(self, snapshot: VosforSnapshot) -> None:
        self.vosfor_status.set(
            f"Workbook: {snapshot.workbook_path} | Importiert: {snapshot.imported_at}"
        )
        self._replace_tree_rows(
            self.top_vosfor_tree,
            [(entry.item_name, entry.vosfor_amount, entry.platinum, entry.vosfor_per_plat) for entry in snapshot.top_entries[:20]],
        )
        self._replace_tree_rows(
            self.baro_tree,
            [(entry.item_name, entry.ducats, entry.platinum, entry.profit) for entry in snapshot.baro_deals[:20]],
        )
        self._replace_tree_rows(
            self.gambling_tree,
            [
                (
                    entry.source,
                    entry.item_name,
                    entry.chance,
                    entry.avg_price_rank0,
                    entry.avg_price_maxed,
                    entry.expected_rank0,
                    entry.expected_maxed,
                    entry.unit_price_maxed,
                )
                for entry in snapshot.gambling_entries
            ],
        )

    def populate_roadmap(self) -> None:
        modules = self.service.list_feature_modules()
        self._replace_tree_rows(
            self.roadmap_tree,
            [
                (f"Phase {module.phase}", module.area, module.name, module.dependencies, module.release)
                for module in modules
            ],
        )

    def populate_requirements(self) -> None:
        integrations = self.service.list_integrations()
        missing = self.service.list_missing_pieces()

        self._replace_tree_rows(
            self.integrations_tree,
            [(item.layer, item.source, item.access, item.priority) for item in integrations],
        )
        self._replace_tree_rows(
            self.missing_tree,
            [(item.area, item.impact, item.needed_from_user, item.notes) for item in missing],
        )

        for child in self.next_steps_container.winfo_children():
            child.destroy()
        self._create_text_block(
            self.next_steps_container,
            [f"{item.step}: {item.outcome}" for item in self.service.list_next_steps()],
        )

    def load_market_search(self, force_refresh: bool = False) -> None:
        query = self.market_query.get().strip()
        if not query:
            self.market_status.set("Bitte einen Market-Suchbegriff eingeben.")
            return

        self.market_status.set(f"Market wird geladen fuer '{query}'...")
        self.market_request_id += 1
        request_id = self.market_request_id
        self.latest_market_request_id = request_id
        self.market_task_queue.put((request_id, query, force_refresh))

    def _market_worker_loop(self) -> None:
        while True:
            task = self.market_task_queue.get()
            if task is None:
                try:
                    self.service.close()
                except Exception:
                    pass
                return

            request_id, query, force_refresh = task
            try:
                snapshot = self.service.search_market(query, force_refresh=force_refresh)
                image_url = snapshot.thumb_url or snapshot.image_url
                image_bytes = self._download_image_bytes(image_url)
                self.market_result_queue.put(("ok", request_id, snapshot, image_bytes))
            except Exception as error:
                self.market_result_queue.put(("error", request_id, str(error), None))

    def _poll_market_results(self) -> None:
        try:
            while True:
                status, request_id, payload, image_bytes = self.market_result_queue.get_nowait()
                if request_id != self.latest_market_request_id:
                    continue
                if status == "ok":
                    assert isinstance(payload, MarketSnapshot)
                    self._populate_market(payload, image_bytes)
                    self._reschedule_market_refresh()
                else:
                    self.market_status.set(str(payload))
                    messagebox.showwarning("Market", str(payload))
        except queue.Empty:
            pass
        self.after(200, self._poll_market_results)

    def _populate_market(self, snapshot: MarketSnapshot, image_bytes: bytes | None) -> None:
        self.current_market_snapshot = snapshot
        self.market_query.set(snapshot.item_name)
        self.market_summary_labels["item"].configure(text=snapshot.item_name)
        self.market_summary_labels["best_price"].configure(text=snapshot.best_price)
        self.market_summary_labels["ingame_sellers"].configure(text=snapshot.ingame_sellers)
        self.market_summary_labels["snapshot"].configure(text=snapshot.fetched_at)
        self.market_status.set(snapshot.status)

        self._set_market_image(image_bytes)
        self._replace_tree_rows(
            self.market_metrics_tree,
            [(metric.label, metric.value, metric.detail) for metric in snapshot.metrics],
        )

        self.market_row_map.clear()
        self.market_orders_tree.delete(*self.market_orders_tree.get_children())
        for order in snapshot.orders:
            row_id = self.market_orders_tree.insert(
                "",
                "end",
                values=(
                    order.seller_name,
                    order.price,
                    order.quantity,
                    order.rank,
                    order.updated_at,
                    order.reputation,
                    order.platform,
                    order.crossplay,
                ),
            )
            self.market_row_map[row_id] = order

        self._replace_tree_rows(
            self.market_recent_tree,
            [
                (
                    trade.captured_at,
                    trade.rank,
                    trade.avg_price,
                    trade.median_price,
                    trade.volume,
                    trade.price_range,
                    trade.moving_average,
                )
                for trade in snapshot.recent_trades
            ],
        )
        self._replace_tree_rows(
            self.market_trend_tree,
            [
                (
                    trade.captured_at,
                    trade.rank,
                    trade.avg_price,
                    trade.median_price,
                    trade.volume,
                    trade.price_range,
                    trade.moving_average,
                )
                for trade in snapshot.trend_trades
            ],
        )

        if snapshot.orders:
            first_row = self.market_orders_tree.get_children()[0]
            self.market_orders_tree.selection_set(first_row)
            self._update_whisper_preview(self.market_row_map[first_row].whisper_text)
        else:
            self._update_whisper_preview("")

    def _set_market_image(self, image_bytes: bytes | None) -> None:
        if not image_bytes:
            self.market_image_ref = None
            self.market_image_label.configure(image="", text="Kein Bild")
            return

        image = Image.open(io.BytesIO(image_bytes))
        image.thumbnail((96, 96))
        self.market_image_ref = ImageTk.PhotoImage(image)
        self.market_image_label.configure(image=self.market_image_ref, text="")

    def _download_image_bytes(self, image_url: str) -> bytes | None:
        if not image_url:
            return None
        request = Request(image_url, headers={"User-Agent": "WarframeCompanion/0.4"})
        try:
            with urlopen(request, timeout=15) as response:
                return response.read()
        except (HTTPError, URLError):
            return None

    def _reschedule_market_refresh(self) -> None:
        if self.market_refresh_after_id is not None:
            self.after_cancel(self.market_refresh_after_id)
            self.market_refresh_after_id = None

        if not self.market_auto_refresh.get():
            return

        delay_seconds = max(30, int(self.market_refresh_seconds.get() or 60))
        self.market_refresh_after_id = self.after(
            delay_seconds * 1000,
            lambda: self.load_market_search(force_refresh=True),
        )

    def _set_market_query(self, item_name: str) -> None:
        self.market_query.set(item_name)
        self.load_market_search(force_refresh=True)

    def _on_market_order_selected(self, _event=None) -> None:
        selection = self.market_orders_tree.selection()
        if not selection:
            return
        order = self.market_row_map.get(selection[0])
        if order is None:
            return
        self._update_whisper_preview(order.whisper_text)

    def _update_whisper_preview(self, whisper_text: str) -> None:
        self.whisper_text.delete("1.0", "end")
        self.whisper_text.insert("1.0", whisper_text)

    def _copy_selected_whisper(self, _event=None) -> None:
        selection = self.market_orders_tree.selection()
        if not selection:
            return
        order = self.market_row_map.get(selection[0])
        if order is None:
            return
        self.clipboard_clear()
        self.clipboard_append(order.whisper_text)
        self.market_status.set(f"Whisper fuer {order.seller_name} in die Zwischenablage kopiert.")
        self._update_whisper_preview(order.whisper_text)

    def load_relic_search(self) -> None:
        try:
            snapshot = self.service.search_relic(self.relic_query.get())
        except LookupError as error:
            self.relic_status.set(str(error))
            messagebox.showwarning("Relic Search", str(error))
            return

        self.relic_query.set(snapshot.relic_name)
        self._replace_tree_rows(
            self.relic_tree,
            [(drop.rarity, drop.reward, drop.chance) for drop in snapshot.drops],
        )
        self.relic_status.set(f"{snapshot.relic_name}: {len(snapshot.drops)} Rewards geladen.")

    def _create_text_block(self, parent: tk.Misc, lines: list[str]) -> None:
        for line in lines:
            tk.Label(
                parent,
                text=f"- {line}",
                font=("Segoe UI", 10),
                bg="#18212d",
                fg="#dbe7f7",
                wraplength=1220,
                justify="left",
            ).pack(anchor="w", pady=2)

    @staticmethod
    def _replace_tree_rows(tree: ttk.Treeview, rows: list[tuple[object, ...]]) -> None:
        tree.delete(*tree.get_children())
        for row in rows:
            tree.insert("", "end", values=row)

    def _on_close(self) -> None:
        if self.market_refresh_after_id is not None:
            self.after_cancel(self.market_refresh_after_id)
            self.market_refresh_after_id = None
        self.market_task_queue.put(None)
        self.destroy()


def main() -> None:
    service = WarframeDataService()
    app = WarframeAssistantApp(service)
    app.mainloop()
