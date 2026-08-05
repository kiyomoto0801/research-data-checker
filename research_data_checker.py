#!/usr/bin/env python3
"""Research Data Checker: statistics and basic quality checks."""

import argparse
import math
import sys
from pathlib import Path

import pandas as pd


def load_data(path, sheet=0):
    suffix = path.suffix.lower()
    if suffix == ".csv":
        try:
            return pd.read_csv(path)
        except UnicodeDecodeError:
            return pd.read_csv(path, encoding="cp932")
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path, sheet_name=sheet)
    raise ValueError("Supported formats: .csv, .xlsx, .xls")


def summarize(df):
    rows = []
    total = len(df)

    for column in df.columns:
        series = df[column]
        missing = int(series.isna().sum())
        base = {
            "variable": column,
            "rows": total,
            "non_missing": int(series.notna().sum()),
            "missing": missing,
            "missing_rate_percent": round(
                missing / total * 100, 2
            ) if total else 0,
            "unique": int(series.nunique(dropna=True)),
            "sample_values": " | ".join(
                series.dropna()
                .astype(str)
                .drop_duplicates()
                .head(3)
                .tolist()
            ),
        }

        if pd.api.types.is_numeric_dtype(series):
            clean = pd.to_numeric(series, errors="coerce").dropna()
            counts = clean.value_counts()

            def value_or_blank(value):
                return "" if pd.isna(value) else round(float(value), 3)

            row = {
                **base,
                "type": "numeric",
                "mean": value_or_blank(clean.mean()),
                "std": value_or_blank(clean.std()),
                "min": value_or_blank(clean.min()),
                "median": value_or_blank(clean.median()),
                "max": value_or_blank(clean.max()),
                "mode": value_or_blank(
                    counts.index[0] if not counts.empty else None
                ),
                "mode_count": int(counts.iloc[0]) if not counts.empty else 0,
            }
        else:
            counts = series.dropna().astype(str).value_counts()
            row = {
                **base,
                "type": "categorical",
                "mean": "",
                "std": "",
                "min": "",
                "median": "",
                "max": "",
                "mode": counts.index[0] if not counts.empty else "",
                "mode_count": int(counts.iloc[0]) if not counts.empty else 0,
            }
        rows.append(row)

    order = [
        "variable", "type", "rows", "non_missing", "missing",
        "missing_rate_percent", "unique", "mean", "std", "min",
        "median", "max", "mode", "mode_count", "sample_values",
    ]
    return pd.DataFrame(rows)[order]


def check_quality(df, threshold=0.10, id_cols=None):
    warnings = []

    def warn(level, variable, issue, details):
        warnings.append({
            "level": level,
            "variable": variable,
            "issue": issue,
            "details": details,
        })

    duplicate_rows = int(df.duplicated().sum())
    if duplicate_rows:
        warn(
            "WARNING", "(all columns)", "duplicate_rows",
            f"{duplicate_rows} completely duplicated row(s) found.",
        )

    for column in df.columns:
        series = df[column]
        rate = series.isna().mean() if len(df) else 0

        if rate > threshold:
            warn(
                "WARNING", column, "high_missing_rate",
                f"{rate:.1%} missing; threshold is {threshold:.1%}.",
            )

        if series.notna().any() and series.nunique(dropna=True) == 1:
            warn(
                "INFO", column, "constant_column",
                "Only one non-missing value is present.",
            )

        if pd.api.types.is_numeric_dtype(series):
            numeric = pd.to_numeric(series, errors="coerce")
            negatives = int((numeric < 0).sum())
            infinite = int(
                numeric.dropna()
                .map(lambda value: not math.isfinite(value))
                .sum()
            )

            if negatives:
                warn(
                    "CHECK", column, "negative_values",
                    f"{negatives} negative value(s); verify whether valid.",
                )
            if infinite:
                warn(
                    "WARNING", column, "infinite_values",
                    f"{infinite} infinite value(s) found.",
                )

    if id_cols:
        missing_cols = [col for col in id_cols if col not in df.columns]
        if missing_cols:
            warn(
                "ERROR", ", ".join(missing_cols), "missing_id_columns",
                "Specified ID column(s) do not exist.",
            )
        else:
            duplicates = int(
                df.duplicated(subset=id_cols, keep=False).sum()
            )
            if duplicates:
                warn(
                    "WARNING", " × ".join(id_cols),
                    "duplicate_id_combination",
                    f"{duplicates} row(s) have duplicated ID combinations.",
                )

    if not warnings:
        warn(
            "OK", "", "no_common_issues",
            "No common data-quality issues were detected.",
        )
    return warnings


def save_results(summary, warnings, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    excel_path = output_dir / "summary.xlsx"
    text_path = output_dir / "warnings.txt"
    warning_df = pd.DataFrame(warnings)

    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="Summary", index=False)
        warning_df.to_excel(writer, sheet_name="Warnings", index=False)

        for sheet in writer.book.worksheets:
            sheet.freeze_panes = "A2"
            sheet.auto_filter.ref = sheet.dimensions
            for cells in sheet.columns:
                width = max(
                    len(str(cell.value or "")) for cell in cells
                ) + 2
                sheet.column_dimensions[
                    cells[0].column_letter
                ].width = min(width, 45)

    lines = [
        f"[{item['level']}] {item['variable']}: {item['details']}"
        for item in warnings
    ]
    text_path.write_text("\n".join(lines), encoding="utf-8")
    return excel_path, text_path


def main():
    parser = argparse.ArgumentParser(
        description="Create statistics and data-quality warnings."
    )
    parser.add_argument("input_file", type=Path)
    parser.add_argument(
        "--output-dir", type=Path, default=Path("output")
    )
    parser.add_argument(
        "--missing-threshold", type=float, default=0.10
    )
    parser.add_argument("--id-cols", nargs="+")
    parser.add_argument("--sheet", default="0")
    args = parser.parse_args()

    if not args.input_file.exists():
        parser.error(f"File not found: {args.input_file}")
    if not 0 <= args.missing_threshold <= 1:
        parser.error("--missing-threshold must be between 0 and 1")

    sheet = int(args.sheet) if args.sheet.isdigit() else args.sheet

    try:
        df = load_data(args.input_file, sheet)
        summary = summarize(df)
        warnings = check_quality(
            df, args.missing_threshold, args.id_cols
        )
        excel_path, text_path = save_results(
            summary, warnings, args.output_dir
        )
    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print(f"Rows: {len(df):,} | Columns: {len(df.columns):,}")
    print(f"Summary: {excel_path}")
    print(f"Warnings: {text_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
