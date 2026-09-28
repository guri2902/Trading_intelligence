from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
orb = ROOT / "backend" / "app" / "strategies" / "orb.py"
retest = ROOT / "backend" / "app" / "strategies" / "orb_retest.py"

def patch(path, old, new, suffix):
    if not path.exists():
        raise SystemExit(f"ERROR: missing {path}")
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"ERROR: expected block not found in {path}")
    backup = path.with_suffix(path.suffix + suffix)
    if not backup.exists():
        shutil.copy2(path, backup)
    path.write_text(text.replace(old, new, 1), encoding="utf-8")

orb_old = """        opening = candles[:self.opening_bars]
        or_high = max(float(x["high"]) for x in opening)
        or_low = min(float(x["low"]) for x in opening)
"""
orb_new = """        from datetime import datetime
        latest_ts = candles[-1].get("timestamp")
        if isinstance(latest_ts, str):
            latest_ts = datetime.fromisoformat(latest_ts.replace("Z", "+00:00"))
        session_date = latest_ts.date() if hasattr(latest_ts, "date") else None
        session_candles = []
        for item in candles:
            ts = item.get("timestamp")
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if session_date is None or ts.date() == session_date:
                session_candles.append(item)
        if len(session_candles) <= self.opening_bars:
            return StrategySetup(
                strategy=self.name,
                direction="NONE",
                state="NO_SETUP",
                wait_for=["Current-session opening range completion"],
            )
        opening = session_candles[:self.opening_bars]
        or_high = max(float(x["high"]) for x in opening)
        or_low = min(float(x["low"]) for x in opening)
"""

retest_old = """        opening = candles[:self.opening_bars]
        hi = max(float(x["high"]) for x in opening)
        lo = min(float(x["low"]) for x in opening)

        recent = candles[-self.retest_bars:]
"""
retest_new = """        from datetime import datetime
        latest_ts = candles[-1].get("timestamp")
        if isinstance(latest_ts, str):
            latest_ts = datetime.fromisoformat(latest_ts.replace("Z", "+00:00"))
        session_date = latest_ts.date() if hasattr(latest_ts, "date") else None
        session_candles = []
        for item in candles:
            ts = item.get("timestamp")
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if session_date is None or ts.date() == session_date:
                session_candles.append(item)
        if len(session_candles) < self.opening_bars + self.retest_bars + 1:
            return StrategySetup(
                strategy=self.name,
                direction="NONE",
                state="NO_SETUP",
                wait_for=["Current-session opening range + retest candles"],
            )
        opening = session_candles[:self.opening_bars]
        hi = max(float(x["high"]) for x in opening)
        lo = min(float(x["low"]) for x in opening)
        recent = session_candles[-self.retest_bars:]
"""

patch(orb, orb_old, orb_new, ".strategyqualityfinalbak")
patch(retest, retest_old, retest_new, ".strategyqualityfinalbak")
print("[OK] ORB and ORB_RETEST now use current-session opening ranges.")
