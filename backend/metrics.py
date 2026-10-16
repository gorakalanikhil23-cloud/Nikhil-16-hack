"""Operational capacity metrics and risk classification."""

from pathlib import Path

import pandas as pd


# Planning assumptions for a single operating shift.
SHIFT_MINUTES = 480
EMERGENCY_WEIGHT = 45
WARNING_THRESHOLD = 0.8
CRITICAL_THRESHOLD = 1.0

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "operations.csv"
RISK_ORDER = {"Critical": 0, "Warning": 1, "Normal": 2}


def _with_metrics(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["demand_minutes"] = (
        result["appointments"] * result["avg_task_minutes"]
        + result["emergency_cases"] * EMERGENCY_WEIGHT
    )
    result["capacity_minutes"] = result["staff_available"] * SHIFT_MINUTES
    result["utilization"] = result["demand_minutes"] / result["capacity_minutes"]
    result["risk"] = result["utilization"].map(
        lambda value: (
            "Critical"
            if value > CRITICAL_THRESHOLD
            else "Warning"
            if value >= WARNING_THRESHOLD
            else "Normal"
        )
    )
    result["_risk_order"] = result["risk"].map(RISK_ORDER)
    return result.sort_values(
        ["_risk_order", "utilization"], ascending=[True, False]
    ).drop(columns="_risk_order").reset_index(drop=True)


def load_data(path: Path = DATA_PATH) -> pd.DataFrame:
    """Load synthetic operations records and reject malformed/empty data."""
    frame = pd.read_csv(path, parse_dates=["date"])
    required = {
        "date",
        "department",
        "appointments",
        "staff_available",
        "avg_task_minutes",
        "emergency_cases",
    }
    if frame.empty or not required.issubset(frame.columns):
        raise ValueError("Operations data is empty or missing required columns.")
    if (frame["staff_available"] <= 0).any():
        raise ValueError("Every department must have at least one available staff member.")
    return frame


def today_metrics(frame: pd.DataFrame | None = None) -> pd.DataFrame:
    data = frame if frame is not None else load_data()
    latest_date = data["date"].max()
    today = data.loc[data["date"] == latest_date].copy()
    return _with_metrics(today)


def forecast_metrics(frame: pd.DataFrame | None = None) -> pd.DataFrame:
    """Forecast from the previous seven days' average workload and capacity inputs."""
    data = frame if frame is not None else load_data()
    latest_date = data["date"].max()
    history = data.loc[data["date"] < latest_date].copy()
    last_seven_days = history["date"].drop_duplicates().sort_values().tail(7)
    history = history.loc[history["date"].isin(last_seven_days)]
    forecast = (
        history.groupby("department", as_index=False)
        .agg(
            appointments=("appointments", "mean"),
            staff_available=("staff_available", "mean"),
            avg_task_minutes=("avg_task_minutes", "mean"),
            emergency_cases=("emergency_cases", "mean"),
        )
    )
    forecast["date"] = latest_date
    return _with_metrics(forecast)
