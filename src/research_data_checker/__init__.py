"""Research Data Checker package."""

from .checker import WarningRecord, check_quality, load_data, save_results, summarize

__all__ = [
    "WarningRecord",
    "check_quality",
    "load_data",
    "save_results",
    "summarize",
]

__version__ = "0.1.0"
