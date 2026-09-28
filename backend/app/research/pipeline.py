from __future__ import annotations

from .scoring import score_backtest
from .walk_forward import walk_forward_splits, summarize_splits


class WalkForwardResearchPipeline:
    def run(
        self,
        rows,
        *,
        train_size,
        validation_size,
        test_size,
        train_fn,
        validation_fn,
        test_fn,
        step=None,
        expanding=True,
        min_trades=30,
    ):
        splits = walk_forward_splits(
            rows,
            train_size=train_size,
            validation_size=validation_size,
            test_size=test_size,
            step=step,
            expanding=expanding,
        )

        reports = []

        for split in splits:
            train_result = train_fn(split.train)
            validation_result = validation_fn(
                split.validation,
                train_result,
            )
            test_result = test_fn(
                split.test,
                train_result,
            )

            train_score = score_backtest(
                train_result.metrics,
                min_trades=min_trades,
            )
            validation_score = score_backtest(
                validation_result.metrics,
                min_trades=min_trades,
            )
            test_score = score_backtest(
                test_result.metrics,
                min_trades=min_trades,
            )

            reports.append({
                "split_id": split.split_id,
                "train": {
                    "score": train_score.__dict__,
                    "metrics": train_result.metrics.model_dump(mode="json"),
                },
                "validation": {
                    "score": validation_score.__dict__,
                    "metrics": validation_result.metrics.model_dump(mode="json"),
                },
                "oos": {
                    "score": test_score.__dict__,
                    "metrics": test_result.metrics.model_dump(mode="json"),
                },
            })

        return {
            "splits": summarize_splits(splits),
            "reports": reports,
            "passed_splits": sum(
                1
                for r in reports
                if r["oos"]["score"]["passed"]
            ),
        }
