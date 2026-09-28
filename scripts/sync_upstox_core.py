from __future__ import annotations

from app.instruments.upstox_master import (
    UpstoxInstrumentMaster,
    default_nse_index_and_fo_filters,
)


def main() -> None:
    filters = default_nse_index_and_fo_filters()

    result = UpstoxInstrumentMaster().sync(**filters)
    print(result)


if __name__ == "__main__":
    main()
