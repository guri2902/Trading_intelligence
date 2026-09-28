
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock

from .models import (
    StrategyCreateRequest,
    StrategyDefinition,
    StrategyUpdateRequest,
    StrategyVersion,
)


class StrategyStore:
    def __init__(self, root: str | None = None) -> None:
        self.root = Path(root or "data/strategies")
        self.file = self.root / "strategies.json"
        self._lock = RLock()
        self.root.mkdir(parents=True, exist_ok=True)
        if not self.file.exists():
            self.file.write_text("[]", encoding="utf-8")

    def _load(self) -> list[StrategyDefinition]:
        raw = json.loads(self.file.read_text(encoding="utf-8"))
        return [StrategyDefinition.model_validate(x) for x in raw]

    def _save(self, strategies: list[StrategyDefinition]) -> None:
        tmp = self.file.with_suffix(".tmp")
        tmp.write_text(
            json.dumps([s.model_dump(mode="json") for s in strategies], indent=2),
            encoding="utf-8",
        )
        tmp.replace(self.file)

    def list(self) -> list[StrategyDefinition]:
        with self._lock:
            return self._load()

    def get(self, strategy_id: str) -> StrategyDefinition:
        with self._lock:
            for item in self._load():
                if item.id == strategy_id:
                    return item
        raise KeyError(strategy_id)

    def create(self, req: StrategyCreateRequest) -> StrategyDefinition:
        now = datetime.now(timezone.utc)
        item = StrategyDefinition(
            name=req.name,
            description=req.description,
            source=req.source,
            instruments=req.instruments,
            timeframe=req.timeframe,
            engine_strategy=req.engine_strategy,
            rules=req.rules,
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            strategies = self._load()
            strategies.append(item)
            self._save(strategies)
        return item

    def update(self, strategy_id: str, req: StrategyUpdateRequest) -> StrategyDefinition:
        now = datetime.now(timezone.utc)
        with self._lock:
            strategies = self._load()
            for idx, item in enumerate(strategies):
                if item.id != strategy_id:
                    continue

                versions = list(item.versions)
                versions.append(
                    StrategyVersion(
                        version=item.version,
                        saved_at=now,
                        snapshot=item.model_dump(mode="json"),
                    )
                )

                updated = item.model_copy(
                    update={
                        "name": req.name,
                        "description": req.description,
                        "source": req.source,
                        "instruments": req.instruments,
                        "timeframe": req.timeframe,
                        "engine_strategy": req.engine_strategy,
                        "rules": req.rules,
                        "version": item.version + 1,
                        "versions": versions,
                        "updated_at": now,
                    }
                )
                strategies[idx] = updated
                self._save(strategies)
                return updated
        raise KeyError(strategy_id)

    def set_status(self, strategy_id: str, status: str) -> StrategyDefinition:
        with self._lock:
            strategies = self._load()
            for idx, item in enumerate(strategies):
                if item.id == strategy_id:
                    updated = item.model_copy(
                        update={
                            "status": status,
                            "updated_at": datetime.now(timezone.utc),
                        }
                    )
                    strategies[idx] = updated
                    self._save(strategies)
                    return updated
        raise KeyError(strategy_id)

    def duplicate(self, strategy_id: str) -> StrategyDefinition:
        source = self.get(strategy_id)
        return self.create(
            StrategyCreateRequest(
                name=f"{source.name} Copy",
                description=source.description,
                source="USER",
                instruments=source.instruments,
                timeframe=source.timeframe,
                engine_strategy=source.engine_strategy,
                rules=source.rules,
            )
        )

    def delete(self, strategy_id: str) -> None:
        with self._lock:
            strategies = self._load()
            updated = [x for x in strategies if x.id != strategy_id]
            if len(updated) == len(strategies):
                raise KeyError(strategy_id)
            self._save(updated)
