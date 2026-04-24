from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


class AppStorage:
    def __init__(self, database_path: Path | None = None) -> None:
        root = Path(__file__).resolve().parent.parent
        self.database_path = database_path or root / "warframe_companion.db"
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _initialize(self) -> None:
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS api_cache (
                    cache_key TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    fetched_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS state_store (
                    state_key TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def get_cached_json(self, cache_key: str, max_age_seconds: int) -> tuple[dict[str, Any] | None, str | None]:
        with sqlite3.connect(self.database_path) as connection:
            row = connection.execute(
                "SELECT payload, fetched_at FROM api_cache WHERE cache_key = ?",
                (cache_key,),
            ).fetchone()

        if row is None:
            return None, None

        payload, fetched_at = row
        fetched_time = datetime.fromisoformat(fetched_at)
        if datetime.now(UTC) - fetched_time > timedelta(seconds=max_age_seconds):
            return None, fetched_at
        return json.loads(payload), fetched_at

    def get_any_cached_json(self, cache_key: str) -> tuple[dict[str, Any] | None, str | None]:
        with sqlite3.connect(self.database_path) as connection:
            row = connection.execute(
                "SELECT payload, fetched_at FROM api_cache WHERE cache_key = ?",
                (cache_key,),
            ).fetchone()

        if row is None:
            return None, None
        payload, fetched_at = row
        return json.loads(payload), fetched_at

    def set_cached_json(self, cache_key: str, payload: dict[str, Any]) -> str:
        fetched_at = datetime.now(UTC).isoformat()
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO api_cache(cache_key, payload, fetched_at)
                VALUES(?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    payload = excluded.payload,
                    fetched_at = excluded.fetched_at
                """,
                (cache_key, json.dumps(payload), fetched_at),
            )
        return fetched_at

    def load_state(self, state_key: str) -> dict[str, Any] | None:
        with sqlite3.connect(self.database_path) as connection:
            row = connection.execute(
                "SELECT payload FROM state_store WHERE state_key = ?",
                (state_key,),
            ).fetchone()

        if row is None:
            return None
        return json.loads(row[0])

    def save_state(self, state_key: str, payload: Any) -> str:
        updated_at = datetime.now(UTC).isoformat()
        normalized = self._normalize(payload)
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO state_store(state_key, payload, updated_at)
                VALUES(?, ?, ?)
                ON CONFLICT(state_key) DO UPDATE SET
                    payload = excluded.payload,
                    updated_at = excluded.updated_at
                """,
                (state_key, json.dumps(normalized), updated_at),
            )
        return updated_at

    def _normalize(self, payload: Any) -> Any:
        if is_dataclass(payload):
            return asdict(payload)
        if isinstance(payload, list):
            return [self._normalize(item) for item in payload]
        if isinstance(payload, dict):
            return {key: self._normalize(value) for key, value in payload.items()}
        return payload
