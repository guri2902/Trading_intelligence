from pathlib import Path
import shutil
import re

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "backend" / "app" / "providers" / "upstox.py"

if not TARGET.exists():
    raise SystemExit(f"ERROR: target not found: {TARGET}")

backup = TARGET.with_suffix(TARGET.suffix + ".historicalchunk_v2.bak")
if not backup.exists():
    shutil.copy2(TARGET, backup)

text = TARGET.read_text(encoding="utf-8")

pattern = re.compile(
    r"    def _historical_candles\(\n"
    r"(?P<body>.*?)"
    r"    def _intraday_candles\(",
    re.DOTALL,
)

match = pattern.search(text)
if not match:
    raise SystemExit(
        "ERROR: Could not locate _historical_candles before _intraday_candles."
    )

new_method = """    def _historical_candles(
        self,
        instrument_key: str,
        unit: str,
        interval: int,
        to_date: date,
        from_date: date | None = None,
    ) -> list[Candle]:
        \"""Fetch historical candles, respecting Upstox V3 range limits.

        Upstox V3 limits minute intervals 1-15 to about one month per request.
        Larger ranges are split into safe 30-day windows.
        \"""
        from datetime import timedelta

        if from_date is not None and unit == "minutes" and int(interval) <= 15:
            result: list[Candle] = []
            cursor = from_date

            while cursor <= to_date:
                chunk_to = min(to_date, cursor + timedelta(days=29))
                url = (
                    f"{UPSTOX_BASE_URL}/v3/historical-candle/"
                    f"{instrument_key}/{unit}/{int(interval)}/"
                    f"{chunk_to.isoformat()}/{cursor.isoformat()}"
                )

                response = self.http.request(
                    "GET",
                    url,
                    headers=self._headers(),
                )

                chunk = self._parse_candles(response.json(), instrument_key)
                result.extend(chunk)
                cursor = chunk_to + timedelta(days=1)

            dedup: dict[object, Candle] = {}
            for candle in result:
                dedup[candle.timestamp] = candle

            return sorted(dedup.values(), key=lambda item: item.timestamp)

        url = (
            f"{UPSTOX_BASE_URL}/v3/historical-candle/"
            f"{instrument_key}/{unit}/{int(interval)}/"
            f"{to_date.isoformat()}"
        )
        if from_date is not None:
            url += f"/{from_date.isoformat()}"

        response = self.http.request(
            "GET",
            url,
            headers=self._headers(),
        )
        return self._parse_candles(response.json(), instrument_key)

    def _intraday_candles("""

text = text[:match.start()] + new_method + text[match.end():]
TARGET.write_text(text, encoding="utf-8")

print("[OK] Upstox historical minute candles now use safe 30-day chunks.")
print("[OK] Large 5-minute ranges are split into valid V3 requests.")
print("[OK] Results are deduplicated and sorted chronologically.")
print(f"[OK] Backup: {backup.name}")
