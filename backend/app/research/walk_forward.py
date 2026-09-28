from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar


T = TypeVar("T")


@dataclass(frozen=True)
class Split(Generic[T]):
    split_id: int
    train: list[T]
    validation: list[T]
    test: list[T]


def walk_forward_splits(
    rows: list[T],
    *,
    train_size: int,
    validation_size: int,
    test_size: int,
    step: int | None = None,
    expanding: bool = True,
) -> list[Split[T]]:
    """
    Chronological walk-forward splitter.

    Example:
      [ TRAIN ][ VAL ][ TEST ]
             -> step
            [ TRAIN ][ VAL ][ TEST ]

    No shuffling. No random split.
    """
    if min(train_size, validation_size, test_size) <= 0:
        raise ValueError("Split sizes must be positive")

    step = step or test_size
    splits: list[Split[T]] = []

    start = 0
    split_id = 1

    while True:
        train_start = 0 if expanding else start
        train_end = start + train_size
        validation_end = train_end + validation_size
        test_end = validation_end + test_size

        if test_end > len(rows):
            break

        splits.append(
            Split(
                split_id=split_id,
                train=rows[train_start:train_end],
                validation=rows[train_end:validation_end],
                test=rows[validation_end:test_end],
            )
        )

        split_id += 1
        start += step

    return splits


def summarize_splits(splits: list[Split]) -> dict:
    return {
        "count": len(splits),
        "splits": [
            {
                "split_id": s.split_id,
                "train_size": len(s.train),
                "validation_size": len(s.validation),
                "test_size": len(s.test),
            }
            for s in splits
        ],
    }
