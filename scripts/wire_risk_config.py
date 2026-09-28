
from pathlib import Path

TARGET = Path("backend/app/realtime/pipeline.py")

OLD_IMPORT = "from ..risk.models import AccountRiskContext\n"
NEW_IMPORT = OLD_IMPORT + "from ..risk_config.service import RiskConfigService\n"

OLD_BLOCK = '''def _account_context(option_timestamp: datetime) -> AccountRiskContext:
    return AccountRiskContext(
        equity=float(os.getenv("RISK_EQUITY", "100000")),
        realized_pnl_today=float(
            os.getenv("RISK_REALIZED_PNL", "0")
        ),
        open_risk=float(os.getenv("RISK_OPEN_RISK", "0")),
        open_positions=int(os.getenv("RISK_OPEN_POSITIONS", "0")),
        trades_today=int(os.getenv("RISK_TRADES_TODAY", "0")),
        peak_equity=float(os.getenv("RISK_PEAK_EQUITY", "100000")),
        risk_per_trade_pct=float(
            os.getenv("RISK_PER_TRADE_PCT", "1.0")
        ),
        max_daily_loss=float(
            os.getenv("RISK_MAX_DAILY_LOSS", "2000")
        ),
        daily_profit_lock=float(
            os.getenv("RISK_DAILY_PROFIT_LOCK", "0")
        ),
        max_concurrent_risk=float(
            os.getenv("RISK_MAX_CONCURRENT_RISK", "2000")
        ),
        max_trades_per_day=int(
            os.getenv("RISK_MAX_TRADES_PER_DAY", "5")
        ),
        max_open_positions=int(
            os.getenv("RISK_MAX_OPEN_POSITIONS", "1")
        ),
        max_drawdown_pct=float(
            os.getenv("RISK_MAX_DRAWDOWN_PCT", "5")
        ),
        square_off_time=os.getenv(
            "RISK_SQUARE_OFF_TIME",
            "15:20",
        ),
        market_timestamp=option_timestamp,
        enabled=os.getenv(
            "RISK_ENABLED",
            "true",
        ).lower() == "true",
    )
'''

NEW_BLOCK = '''risk_config_service = RiskConfigService()


def _account_context(option_timestamp: datetime) -> AccountRiskContext:
    cfg = risk_config_service.get()

    # User-facing controls remain cash/lot based. The existing RiskEngine
    # still consumes risk_per_trade_pct, so convert the cash budget internally.
    risk_per_trade_pct = (
        (cfg.per_trade_risk / cfg.capital) * 100.0
        if cfg.capital > 0
        else 0.0
    )

    return AccountRiskContext(
        equity=cfg.capital,
        realized_pnl_today=float(
            os.getenv("RISK_REALIZED_PNL", "0")
        ),
        open_risk=float(os.getenv("RISK_OPEN_RISK", "0")),
        open_positions=int(os.getenv("RISK_OPEN_POSITIONS", "0")),
        trades_today=int(os.getenv("RISK_TRADES_TODAY", "0")),
        peak_equity=float(
            os.getenv("RISK_PEAK_EQUITY", str(cfg.capital))
        ),
        risk_per_trade_pct=risk_per_trade_pct,
        max_daily_loss=cfg.daily_risk_budget,
        daily_profit_lock=float(
            os.getenv("RISK_DAILY_PROFIT_LOCK", "0")
        ),
        max_concurrent_risk=cfg.max_concurrent_risk,
        max_trades_per_day=cfg.max_trades_per_day,
        max_open_positions=cfg.max_open_positions,
        max_drawdown_pct=cfg.max_drawdown_pct,
        square_off_time=cfg.square_off_time,
        market_timestamp=option_timestamp,
        enabled=True,
    )
'''

text = TARGET.read_text(encoding="utf-8")

if "from ..risk_config.service import RiskConfigService" not in text:
    if OLD_IMPORT not in text:
        raise SystemExit("Could not find RiskEngine model import block.")
    text = text.replace(OLD_IMPORT, NEW_IMPORT, 1)

if OLD_BLOCK not in text:
    if "risk_config_service = RiskConfigService()" not in text:
        raise SystemExit("Could not find the existing _account_context block.")
else:
    text = text.replace(OLD_BLOCK, NEW_BLOCK, 1)

TARGET.write_text(text, encoding="utf-8")
print(f"Updated {TARGET}")
