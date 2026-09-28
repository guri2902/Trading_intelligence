from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from .models import InstrumentRecord
from .repository import sync_records


class InstrumentService:
    def sync(self, db: Session, records: list[InstrumentRecord]) -> dict[str, Any]:
        count = sync_records(db, records)
        return {
            "synced": count,
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }
