"""Unit tests for Research Data Checker."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from research_data_checker.checker import (
    check_quality,
    load_data,
    save_results,
    summarize,
)
from research_data_checker.cli import main


def test_load_csv(tmp_path: Path) -> None:
    path = tmp_path / "data.csv"
    path.write_text("id,value\n1,10\n2,20\n", encoding="utf-8")
    frame = load_data(path)
    assert frame.shape == (2, 2)
    assert frame["value"].tolist() == [10, 20]


def test_load_unsupported_extension(tmp_path: Path) -> None:
    path = tmp_path / "data.txt"
    path.write_text("hello", encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported file type"):
        load_data(path)


def test_summarize_numeric_and_categorical() -> None:
    frame = pd.DataFrame(
        {
            "income": [10.0, 20.0, np.nan, 30.0],
            "group": ["A", "A", "B", None],
        }
    )
    result = summarize(frame).set_index("variable")

    assert result.loc["income", "type"] == "numeric"
    assert result.loc["income", "mean"] == 20.0
    assert result.loc["income", "median"] == 20.0
    assert result.loc["income", "missing_rate_percent"] == 25.0
    assert result.loc["group", "type"] == "categorical"
    assert result.loc["group", "mode"] == "A"
    assert result.loc["group", "mode_count"] == 2


def test_quality_checks_find_expected_issues() -> None:
    frame = pd.DataFrame(
        {
            "id": [1, 1, 2, 3, 3],
            "year": [2024, 2024, 2024, 2024, 2024],
            "age": [20, 20, -1, 30, 30],
            "income": [100.0, 100.0, np.nan, np.nan, 50.0],
        }
    )
    issues = {
        item["issue"]
        for item in check_quality(frame, missing_threshold=0.20, id_cols=["id", "year"])
    }

    assert "duplicate_rows" in issues
    assert "high_missing_rate" in issues
    assert "negative_values" in issues
    assert "duplicate_id_combination" in issues


def test_quality_check_reports_missing_id_column() -> None:
    frame = pd.DataFrame({"id": [1, 2]})
    warnings = check_quality(frame, id_cols=["id", "year"])
    assert any(item["issue"] == "missing_id_columns" for item in warnings)


def test_invalid_missing_threshold() -> None:
    with pytest.raises(ValueError, match="between 0 and 1"):
        check_quality(pd.DataFrame({"x": [1]}), missing_threshold=1.1)


def test_save_results(tmp_path: Path) -> None:
    frame = pd.DataFrame({"x": [1, 2, 3]})
    summary = summarize(frame)
    warnings = check_quality(frame)
    excel_path, text_path = save_results(summary, warnings, tmp_path / "out")

    assert excel_path.exists()
    assert text_path.exists()
    assert pd.ExcelFile(excel_path).sheet_names == ["Summary", "Warnings"]
    assert "No common data-quality issues" in text_path.read_text(encoding="utf-8")


def test_cli_smoke_test(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    input_path = tmp_path / "data.csv"
    output_path = tmp_path / "result"
    input_path.write_text("id,value\n1,10\n2,20\n", encoding="utf-8")

    preview_path = tmp_path / "preview.png"
    exit_code = main(
        [
            str(input_path),
            "--output-dir",
            str(output_path),
            "--preview-path",
            str(preview_path),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Rows: 2 | Columns: 2" in captured.out
    assert (output_path / "summary.xlsx").exists()
    assert preview_path.exists()
