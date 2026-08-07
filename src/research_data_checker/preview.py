"""Render the descriptive-statistics summary as a PNG table."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from matplotlib.axes import Axes
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

CORE_COLUMNS = [
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
]

DETAIL_COLUMNS = [
    "variable",
    "mode",
    "mode_count",
    "sample_values",
]


def _display_value(value: object) -> str:
    """Convert a summary value to compact display text."""
    if value is None or pd.isna(value):
        return ""

    if isinstance(value, float):
        return f"{value:,.3f}".rstrip("0").rstrip(".")

    if isinstance(value, int):
        return f"{value:,}"

    return str(value)


def _display_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a string-only DataFrame for the image table."""
    displayed = frame.apply(
        lambda column: column.map(_display_value)
    )

    if "sample_values" in displayed.columns:
        def format_samples(value: str) -> str:
            parts = [
                part.strip()
                for part in str(value).split("|")
                if part.strip()
            ]

            shortened = []
            for part in parts[:3]:
                if len(part) > 14:
                    part = part[:11] + "..."
                shortened.append(part)

            return ", ".join(shortened)

        displayed["sample_values"] = displayed[
            "sample_values"
        ].map(format_samples)

    return displayed


def _column_widths(
    frame: pd.DataFrame,
    maximum: int = 28,
) -> list[float]:
    """Calculate relative column widths."""
    lengths: list[int] = []

    for column in frame.columns:
        cell_lengths = frame[column].map(
            lambda value: max(
                (
                    len(line)
                    for line in str(value).splitlines()
                ),
                default=0,
            )
        )

        lengths.append(
            max(
                len(str(column)),
                min(int(cell_lengths.max()), maximum),
                5,
            )
        )

    total = sum(lengths)
    return [length / total for length in lengths]


def _add_table(
    axis: Axes,
    frame: pd.DataFrame,
    title: str,
) -> None:
    """Draw one formatted summary table."""
    axis.axis("off")
    axis.set_title(
        title,
        fontsize=15,
        fontweight="bold",
        pad=14,
    )

    table = axis.table(
        cellText=frame.values.tolist(),
        colLabels=frame.columns.tolist(),
        cellLoc="center",
        colLoc="center",
        colWidths=_column_widths(frame),
        loc="center",
    )

    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1.0, 1.9)

    for (row, _column), cell in table.get_celld().items():
        if row == 0:
            cell.set_text_props(fontweight="bold")
            cell.set_facecolor("#E6E6E6")
        elif row % 2 == 0:
            cell.set_facecolor("#F7F7F7")


def save_preview_image(
    summary: pd.DataFrame,
    image_path: str | Path,
    source_name: str,
) -> Path:
    """Save all Summary-sheet columns as one PNG image."""
    path = Path(image_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    core = _display_frame(
        summary[CORE_COLUMNS].copy()
    )
    details = _display_frame(
        summary[DETAIL_COLUMNS].copy()
    )

    figure_height = max(
        9.0,
        2.8 + len(summary) * 0.48,
    )

    figure = Figure(
        figsize=(24, figure_height),
        layout="constrained",
    )
    FigureCanvasAgg(figure)

    grid = figure.add_gridspec(
        1,
        2,
        width_ratios=[2.45, 1.0],
    )

    figure.suptitle(
        f"Research Data Checker Summary — {source_name}",
        fontsize=20,
        fontweight="bold",
    )

    _add_table(
        figure.add_subplot(grid[0, 0]),
        core,
        "Descriptive statistics",
    )

    _add_table(
        figure.add_subplot(grid[0, 1]),
        details,
        "Modes and sample values",
    )

    png_path = path.with_suffix(".png")
    svg_path = path.with_suffix(".svg")

    figure.savefig(
        png_path,
        dpi=300,
        bbox_inches="tight",
    )
    figure.savefig(
        svg_path,
        format="svg",
        bbox_inches="tight",
    )

    return svg_path
