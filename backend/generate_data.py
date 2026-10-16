"""Generate reproducible, synthetic hospital operations data."""

from datetime import date, timedelta
from pathlib import Path
import random

import pandas as pd


DEPARTMENTS = [
    "Radiology",
    "Emergency",
    "Laboratory",
    "Cardiology",
    "Pharmacy",
    "Orthopedics",
    "Pediatrics",
    "General OPD",
]
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "operations.csv"


def generate_data(today: date | None = None) -> pd.DataFrame:
    """Return eight days of synthetic operational records, including today."""
    current_day = today or date.today()
    rng = random.Random(42)
    records = []

    normal_ranges = {
        "Radiology": (14, 24, 3),
        "Emergency": (20, 32, 8),
        "Laboratory": (30, 48, 5),
        "Cardiology": (12, 22, 2),
        "Pharmacy": (28, 45, 4),
        "Orthopedics": (12, 24, 2),
        "Pediatrics": (14, 25, 3),
        "General OPD": (32, 52, 5),
    }

    for day_offset in range(7, 0, -1):
        record_date = current_day - timedelta(days=day_offset)
        for department in DEPARTMENTS:
            low, high, emergency_high = normal_ranges[department]
            records.append(
                {
                    "date": record_date.isoformat(),
                    "department": department,
                    "appointments": rng.randint(low, high),
                    "staff_available": rng.randint(3, 6),
                    "avg_task_minutes": rng.randint(12, 20),
                    "emergency_cases": rng.randint(0, emergency_high),
                }
            )

    for department in DEPARTMENTS:
        low, high, emergency_high = normal_ranges[department]
        if department == "Radiology":
            values = (42, 1, 25, 4)
        elif department == "Emergency":
            values = (39, 3, 19, 11)
        elif department == "General OPD":
            values = (58, 4, 18, 4)
        else:
            values = (
                rng.randint(low, high),
                rng.randint(3, 6),
                rng.randint(12, 20),
                rng.randint(0, emergency_high),
            )
        appointments, staff, task_minutes, emergency_cases = values
        records.append(
            {
                "date": current_day.isoformat(),
                "department": department,
                "appointments": appointments,
                "staff_available": staff,
                "avg_task_minutes": task_minutes,
                "emergency_cases": emergency_cases,
            }
        )

    return pd.DataFrame(records)


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    generate_data().to_csv(OUTPUT_PATH, index=False)
    print(f"Wrote synthetic operations data to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
