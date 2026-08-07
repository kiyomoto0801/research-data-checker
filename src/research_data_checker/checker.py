"""Core functions for summarizing and checking research datasets."""

from __future__ import annotations

import math
from pathlib import Path
from typing import NotRequired, TypedDict

import pandas as pd

SUPPORTED_EXTENSIONS = {".csv", ".xlsx"}
SUMMARY_COLUMNS = [
    "variable",
    "type",
    "rows",
    "non_missing",
    "missing",
    "missing_rate_percent",
    "unique",
    "mean",
    "std",
    "min",
    "median",
    "max",
    "mode",
    "mode_count",
    "sample_values",
]


class WarningRecord(TypedDict):
    """Structure of one data-quality warning."""

    level: str
    variable: str
    issue: str
    details: str
    count: NotRequired[int]


def load_data(file_path: str | Path, sheet: str | int = 0) -> pd.DataFrame:
    """Load a CSV or Excel file.

    CSV files are first read as UTF-8. If that fails, CP932 is tried so that
    CSV files exported from Japanese versions of Excel can also be used.
    """
    path = Path(file_path)
    suffix = path.suffix.lower()

    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")
    if suffix not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise ValueError(f"Unsupported file type: {suffix}. Use: {supported}")

    if suffix == ".csv":
        try:
            return pd.read_csv(path)
        except UnicodeDecodeError:
            return pd.read_csv(path, encoding="cp932")

    return pd.read_excel(path, sheet_name=sheet)


def _round_or_blank(value: object, digits: int = 3) -> float | str:
    """Round a finite numeric value or return an empty string."""
    if value is None or pd.isna(value):
        return ""
    number = float(value)
    return round(number, digits) if math.isfinite(number) else number


def _sample_values(series: pd.Series, limit: int = 3) -> str:
    """Return a short display string containing unique sample values."""
    values = series.dropna().astype(str).drop_duplicates().head(limit).tolist()
    return " | ".join(values)


def _summarize_column(series: pd.Series, total_rows: int) -> dict[str, object]:
    """Create one summary record for a DataFrame column."""
    missing = int(series.isna().sum())
    common: dict[str, object] = {
        "variable": str(series.name),
        "rows": total_rows,
        "non_missing": int(series.notna().sum()),
        "missing": missing,
        "missing_rate_percent": round(missing / total_rows * 100, 2)
        if total_rows
        else 0.0,
        "unique": int(series.nunique(dropna=True)),
        "sample_values": _sample_values(series),
    }

    if pd.api.types.is_numeric_dtype(series):
        clean = pd.to_numeric(series, errors="coerce").dropna()
        counts = clean.value_counts()
        return {
            **common,
            "type": "numeric",
            "mean": _round_or_blank(clean.mean()),
            "std": _round_or_blank(clean.std()),
            "min": _round_or_blank(clean.min()),
            "median": _round_or_blank(clean.median()),
            "max": _round_or_blank(clean.max()),
            "mode": _round_or_blank(counts.index[0]) if not counts.empty else "",
            "mode_count": int(counts.iloc[0]) if not counts.empty else 0,
        }

    counts = series.dropna().astype(str).value_counts()
    return {
        **common,
        "type": "categorical",
        "mean": "",
        "std": "",
        "min": "",
        "median": "",
        "max": "",
        "mode": counts.index[0] if not counts.empty else "",
        "mode_count": int(counts.iloc[0]) if not counts.empty else 0,
    }


def summarize(data: pd.DataFrame) -> pd.DataFrame:
    """Return descriptive statistics for every column in *data*."""
    rows = [_summarize_column(data[column], len(data)) for column in data.columns]
    return pd.DataFrame(rows, columns=SUMMARY_COLUMNS)


def _warning(
    level: str,
    variable: str,
    issue: str,
    details: str,
    count: int | None = None,
) -> WarningRecord:
    """Build a consistently formatted warning record."""
    record: WarningRecord = {
        "level": level,
        "variable": variable,
        "issue": issue,
        "details": details,
    }
    if count is not None:
        record["count"] = count
    return record


def check_quality(
    data: pd.DataFrame,
    missing_threshold: float = 0.10,
    id_cols: list[str] | None = None,
) -> list[WarningRecord]:
    """Detect common data-quality issues.

    Warnings indicate values that should be reviewed. They do not prove that
    the data are incorrect; for example, negative growth rates may be valid.
    """
    if not 0 <= missing_threshold <= 1:
        raise ValueError("missing_threshold must be between 0 and 1")

    warnings: list[WarningRecord] = []
    duplicate_rows = int(data.duplicated().sum())
    if duplicate_rows:
        warnings.append(
            _warning(
                "WARNING",
                "(all columns)",
                "duplicate_rows",
                f"{duplicate_rows} completely duplicated row(s) found.",
                duplicate_rows,
            )
        )

    for column in data.columns:
        series = data[column]
        missing_rate = float(series.isna().mean()) if len(data) else 0.0

        if missing_rate > missing_threshold:
            missing_count = int(series.isna().sum())
            warnings.append(
                _warning(
                    "WARNING",
                    str(column),
                    "high_missing_rate",
                    f"{missing_rate:.1%} missing; threshold is {missing_threshold:.1%}.",
                    missing_count,
                )
            )

        if series.notna().any() and series.nunique(dropna=True) == 1:
            warnings.append(
                _warning(
                    "INFO",
                    str(column),
                    "constant_column",
                    "Only one non-missing value is present.",
                )
            )

        if pd.api.types.is_numeric_dtype(series):
            numeric = pd.to_numeric(series, errors="coerce")
            negative_count = int((numeric < 0).sum())
            infinite_count = int(
                numeric.dropna().map(lambda value: not math.isfinite(float(value))).sum()
            )

            if negative_count:
                warnings.append(
                    _warning(
                        "CHECK",
                        str(column),
                        "negative_values",
                        f"{negative_count} negative value(s); verify whether valid.",
                        negative_count,
                    )
                )
            if infinite_count:
                warnings.append(
                    _warning(
                        "WARNING",
                        str(column),
                        "infinite_values",
                        f"{infinite_count} infinite value(s) found.",
                        infinite_count,
                    )
                )

    if id_cols:
        missing_columns = [column for column in id_cols if column not in data.columns]
        if missing_columns:
            warnings.append(
                _warning(
                    "ERROR",
                    ", ".join(missing_columns),
                    "missing_id_columns",
                    "Specified ID column(s) do not exist.",
                )
            )
        else:
            duplicated_ids = int(data.duplicated(subset=id_cols, keep=False).sum())
            if duplicated_ids:
                warnings.append(
                    _warning(
                        "WARNING",
                        " x ".join(id_cols),
                        "duplicate_id_combination",
                        f"{duplicated_ids} row(s) have duplicated ID combinations.",
                        duplicated_ids,
                    )
                )

    if not warnings:
        warnings.append(
            _warning(
                "OK",
                "",
                "no_common_issues",
                "No common data-quality issues were detected.",
            )
        )
    return warnings


def save_results(
    summary: pd.DataFrame,
    warnings: list[WarningRecord],
    output_dir: str | Path,
) -> tuple[Path, Path]:
    """Save an Excel workbook and a plain-text warning report."""
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    excel_path = directory / "summary.xlsx"
    text_path = directory / "warnings.txt"
    warning_frame = pd.DataFrame(warnings)

    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="Summary", index=False)
        warning_frame.to_excel(writer, sheet_name="Warnings", index=False)

        for worksheet in writer.book.worksheets:
            worksheet.freeze_panes = "A2"
            worksheet.auto_filter.ref = worksheet.dimensions
            for cells in worksheet.columns:
                width = max(len(str(cell.value or "")) for cell in cells) + 2
                worksheet.column_dimensions[cells[0].column_letter].width = min(width, 45)

    lines = [
        f"[{item['level']}] {item['variable']}: {item['details']}"
        for item in warnings
    ]
    text_path.write_text("\n".join(lines), encoding="utf-8")
    return excel_path, text_path
