"""
Generate synthetic historical crowd data for ML training.
"""
import random
from datetime import date, timedelta

import numpy as np
import pandas as pd

# Requirement 1.3 / 2.9: crowd level thresholds.
CROWD_BANDS = ((10, "low", 0), (25, "medium", 1), (40, "high", 2))

WEATHER_BY_SEASON = {
    "monsoon": ("rainy", "cloudy", "clear"),
    "winter": ("cold", "clear", "cloudy"),
    "default": ("clear", "hot", "cloudy"),
}


def _classify(count: int):
    """Map a patient count onto a crowd level label and code."""
    for ceiling, label, code in CROWD_BANDS:
        if count <= ceiling:
            return label, code
    return "critical", 3


def _pick_weather(month: int) -> str:
    if month in (6, 7, 8):
        options = WEATHER_BY_SEASON["monsoon"]
    elif month in (12, 1, 2):
        options = WEATHER_BY_SEASON["winter"]
    else:
        options = WEATHER_BY_SEASON["default"]
    return random.choice(options)


def _build_record(current_date: date, dept_id: int, hour: int) -> dict:
    """Create one department-hour observation with realistic multipliers."""
    day_of_week = current_date.weekday()
    month = current_date.month
    is_weekend = day_of_week >= 5

    # Department size varies, which widens the spread of crowd levels so all
    # four classes are well represented (Requirement 2.9).
    base = 15 + (dept_id - 1) * 3
    dept_factor = 1.0 + (dept_id % 3) * 0.2

    # Requirement 2.4 / 2.5: peak-hour multipliers.
    if 9 <= hour <= 11:
        time_factor = 1.8
    elif 14 <= hour <= 16:
        time_factor = 1.5
    elif hour == 8 or hour >= 18:
        time_factor = 0.4
    elif 12 <= hour <= 13:
        time_factor = 0.7  # lunch dip
    else:
        time_factor = 1.0

    # Requirement 2.3 / 2.6: Monday surge and weekend reduction.
    if day_of_week == 0:
        day_factor = 1.5
    elif day_of_week == 4:
        day_factor = 1.2
    elif is_weekend:
        day_factor = 0.3
    else:
        day_factor = 1.0

    # Requirement 2.7: flu season.
    if month in (11, 12, 1, 2):
        season_factor = 1.4
    elif month in (6, 7):
        season_factor = 1.15
    else:
        season_factor = 1.0

    holidays = _build_record.holidays
    is_holiday = current_date in holidays
    holiday_factor = 0.2 if is_holiday else 1.0

    temperature = 25 + 10 * np.sin(2 * np.pi * (month - 1) / 12)
    temperature += random.uniform(-3, 3)

    count = int(
        base
        * dept_factor
        * time_factor
        * day_factor
        * season_factor
        * holiday_factor
        + random.gauss(0, 3)
    )
    count = max(0, count)

    level, level_code = _classify(count)

    return {
        "department_id": dept_id,
        "log_date": current_date,
        "hour": hour,
        "day_of_week": day_of_week,
        "month": month,
        "is_holiday": int(is_holiday),
        "is_weekend": int(is_weekend),
        "is_monday": 1 if day_of_week == 0 else 0,
        "is_morning_peak": 1 if 9 <= hour <= 11 else 0,
        "is_afternoon_peak": 1 if 14 <= hour <= 16 else 0,
        "is_flu_season": 1 if month in (11, 12, 1, 2) else 0,
        "temperature": round(temperature, 1),
        "weather": _pick_weather(month),
        "patient_count": count,
        "avg_wait_time": round(count * random.uniform(1.5, 3.0), 1),
        "crowd_level": level,
        "crowd_level_code": level_code,
    }


_build_record.holidays = set()


def generate_crowd_data(
    num_days: int = 365,
    num_departments: int = 6,
    observations_per_hour: int = 2,
) -> pd.DataFrame:
    """
    Generate realistic synthetic crowd data.

    Requirement 2.1 asks for at least 50,000 records, while Requirement 2.2
    fixes the grid at 365 days x 6 departments x 13 hours = 28,470 slots.
    Those two only reconcile with more than one observation per slot, so each
    department-hour is sampled `observations_per_hour` times with independent
    noise (half-hourly readings). The default of 2 yields 56,940 records,
    matching the figure quoted in the specification glossary.
    """
    random.seed(42)
    np.random.seed(42)

    start_date = date.today() - timedelta(days=num_days)

    # Two notional public holidays per month.
    holidays = set()
    for month in range(1, 13):
        holidays.add(date(start_date.year, month, 1))
        holidays.add(date(start_date.year, month, 15))
    _build_record.holidays = holidays

    records = []
    for day_offset in range(num_days):
        current_date = start_date + timedelta(days=day_offset)
        for dept_id in range(1, num_departments + 1):
            # `current_count` must be something the system actually knows at
            # prediction time, so it carries the previous hour's volume for
            # this department rather than the hour being predicted. Training on
            # the same hour's count would leak the label (which is a pure
            # threshold of it) and would not match what CrowdPredictor passes
            # in at inference time.
            previous_count = 0
            for hour in range(8, 21):  # 8 AM to 8 PM = 13 hours
                hour_counts = []
                for _ in range(observations_per_hour):
                    record = _build_record(current_date, dept_id, hour)
                    record["current_count"] = previous_count
                    hour_counts.append(record["patient_count"])
                    records.append(record)
                previous_count = int(sum(hour_counts) / len(hour_counts))

    df = pd.DataFrame(records)
    print(f"Generated {len(df):,} records")
    print(f"   Days: {num_days} | Departments: {num_departments} | "
          f"Hours/day: 13 | Observations/hour: {observations_per_hour}")
    print(f"Crowd level distribution:\n{df['crowd_level'].value_counts()}")
    return df


if __name__ == "__main__":
    df = generate_crowd_data()
    df.to_csv("crowd_data.csv", index=False)
    print("Saved to crowd_data.csv")
