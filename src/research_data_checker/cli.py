"""Command-line interface for Research Data Checker."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .checker import check_quality, load_data, save_results, summarize
from .preview import save_preview_image


def _parse_sheet(value: str) -> str | int:
    """Convert a numeric sheet argument to a zero-based integer index."""
    return int(value) if value.isdigit() else value


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="research-data-checker",
        description="Create descriptive statistics and data-quality warnings.",
    )
    parser.add_argument("input_file", type=Path, help="CSV or Excel input file")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Output directory (default: output)",
    )
    parser.add_argument(
        "--preview-path",
        type=Path,
        default=Path("docs/images/example-output.png"),
        help="PNG preview path (default: docs/images/example-output.png)",
    )
    parser.add_argument(
        "--missing-threshold",
        type=float,
        default=0.10,
        help="Missing-rate warning threshold from 0 to 1 (default: 0.10)",
    )
    parser.add_argument(
        "--id-cols",
        nargs="+",
        default=None,
        help="Columns that should uniquely identify each row",
    )
    parser.add_argument(
        "--sheet",
        default="0",
        help="Excel sheet name or zero-based sheet number (default: 0)",
    )
    parser.add_argument("--version", action="version", version=__version__)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the command-line application and return an exit status."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not 0 <= args.missing_threshold <= 1:
        parser.error("--missing-threshold must be between 0 and 1")

    try:
        data = load_data(args.input_file, _parse_sheet(args.sheet))
        summary = summarize(data)
        warnings = check_quality(data, args.missing_threshold, args.id_cols)
        excel_path, warning_path = save_results(summary, warnings, args.output_dir)
        preview_path = save_preview_image(
            summary,
            args.preview_path,
            args.input_file.name,
        )
    except (FileNotFoundError, ValueError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print(f"Rows: {len(data):,} | Columns: {len(data.columns):,}")
    print(f"Summary: {excel_path}")
    print(f"Warnings: {warning_path}")
    print(f"Preview: {preview_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
