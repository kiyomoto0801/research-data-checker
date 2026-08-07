"""Measure processing time and verify detection of known issues."""

from __future__ import annotations

import json
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from research_data_checker import check_quality, summarize

ROOT = Path(__file__).resolve().parents[1]
BENCHMARKS = ROOT / "benchmarks"
SIZES = [100, 1_000, 10_000, 100_000]
REPEATS = 5


def make_data(rows: int, seed: int = 42) -> pd.DataFrame:
    """Create reproducible synthetic panel-like data."""
    rng = np.random.default_rng(seed)
    frame = pd.DataFrame(
        {
            "household_id": np.arange(rows),
            "year": rng.integers(2020, 2026, rows),
            "age": rng.integers(18, 90, rows),
            "income": rng.normal(300, 80, rows),
            "gender": rng.choice(["Female", "Male"], rows),
            "region": rng.choice(["A", "B", "C", "D"], rows),
        }
    )
    frame.loc[frame.index[::20], "income"] = np.nan
    return frame


def measure(rows: int) -> float:
    """Return median processing time in seconds."""
    data = make_data(rows)
    summarize(data)
    check_quality(data)
    timings = []
    for _ in range(REPEATS):
        start = time.perf_counter()
        summarize(data)
        check_quality(data)
        timings.append(time.perf_counter() - start)
    return float(np.median(timings))


def detection_check() -> dict[str, object]:
    """Insert four known issue types and test whether all are detected."""
    data = pd.DataFrame(
        {
            "id": [1, 1, 2, 3, 3],
            "year": [2024, 2024, 2024, 2024, 2024],
            "age": [20, 20, -1, 30, 30],
            "income": [100.0, 100.0, np.nan, np.nan, 50.0],
        }
    )
    expected = {
        "duplicate_rows",
        "high_missing_rate",
        "negative_values",
        "duplicate_id_combination",
    }
    detected = {
        warning["issue"]
        for warning in check_quality(data, missing_threshold=0.20, id_cols=["id", "year"])
    }
    found = expected & detected
    return {
        "expected_issue_types": len(expected),
        "detected_issue_types": len(found),
        "detection_rate_percent": len(found) / len(expected) * 100,
        "detected": sorted(found),
    }


def main() -> None:
    """Run the benchmark and save CSV, JSON, and vector PDF outputs."""
    BENCHMARKS.mkdir(exist_ok=True)
    results = pd.DataFrame(
        {"rows": SIZES, "seconds": [measure(size) for size in SIZES]}
    )
    detection = detection_check()
    results.to_csv(BENCHMARKS / "benchmark_results.csv", index=False)
    (BENCHMARKS / "detection_results.json").write_text(
        json.dumps(detection, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    figure, axis = plt.subplots(figsize=(5.8, 3.4))
    axis.plot(results["rows"], results["seconds"], marker="o")
    axis.set_xscale("log")
    axis.set_xlabel("Number of rows (log scale)")
    axis.set_ylabel("Median processing time (seconds)")
    axis.set_title("Research Data Checker processing time")
    axis.grid(True, alpha=0.3)
    figure.tight_layout()
    figure.savefig(BENCHMARKS / "benchmark.pdf", bbox_inches="tight")
    figure.savefig(BENCHMARKS / "benchmark.png", dpi=180, bbox_inches="tight")
    plt.close(figure)

    print(results.to_string(index=False))
    print(json.dumps(detection, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
