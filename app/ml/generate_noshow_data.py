"""
Generate a synthetic no-show dataset in the Kaggle schema.

Use this when the real Kaggle dataset is unavailable:
    https://www.kaggle.com/datasets/joniarroba/noshowappointments

IMPORTANT: the resulting model only learns the relationships encoded in
this generator. Accuracy scores from synthetic data are NOT evidence about
real patient behaviour. Replace data/raw/no_show.csv with the genuine
Kaggle export before relying on any prediction operationally.

Output columns match the Kaggle file exactly so preprocess_noshow.py runs
unchanged:
    PatientId, AppointmentID, Gender, ScheduledDay, AppointmentDay, Age,
    Neighbourhood, Scholarship, Hipertension, Diabetes, Alcoholism,
    Handcap, SMS_received, No-show
"""
import argparse
import os

import numpy as np
import pandas as pd

NEIGHBOURHOODS = [
    "JARDIM CAMBURI", "MARIA ORTIZ", "RESISTENCIA", "JARDIM DA PENHA",
    "ITARARE", "CENTRO", "TABUAZEIRO", "SANTA MARTHA", "JESUS DE NAZARETH",
    "BONFIM", "SANTO ANTONIO", "CARATOIRA", "SAO PEDRO", "ILHA DO PRINCIPE",
    "ROMAO", "GURIGICA", "NOVA PALESTINA", "DA PENHA", "SANTOS DUMONT",
    "CONSOLACAO",
]

# Baseline no-show probability, then additive effects. These mirror the
# widely reported trends in the Kaggle dataset (~20% overall no-show rate).
BASE_RATE = 0.10


def generate(n_records=110_000, seed=42):
    rng = np.random.default_rng(seed)

    # ----- patient population -----
    n_patients = max(1, n_records // 3)
    patient_ids = rng.integers(10_000_000, 99_999_999_999, size=n_patients)

    patient_age = np.clip(rng.gamma(shape=4.0, scale=9.5, size=n_patients), 0, 100).astype(int)
    patient_gender = rng.choice(["F", "M"], size=n_patients, p=[0.65, 0.35])
    patient_hood = rng.choice(NEIGHBOURHOODS, size=n_patients)

    # Chronic conditions scale with age.
    age_factor = patient_age / 100.0
    hypertension = (rng.random(n_patients) < (0.02 + 0.45 * age_factor)).astype(int)
    diabetes = (rng.random(n_patients) < (0.01 + 0.18 * age_factor)).astype(int)
    alcoholism = (rng.random(n_patients) < 0.03).astype(int)
    handicap = (rng.random(n_patients) < 0.02).astype(int)
    scholarship = (rng.random(n_patients) < 0.10).astype(int)

    # A latent per-patient reliability trait: some people habitually miss.
    reliability = rng.beta(a=5.0, b=2.0, size=n_patients)

    # ----- appointments -----
    idx = rng.integers(0, n_patients, size=n_records)

    scheduled_day = pd.Timestamp("2016-01-01") + pd.to_timedelta(
        rng.integers(0, 180, size=n_records), unit="D"
    )

    # Booking gap: heavily skewed toward same-day / short notice.
    gap = rng.choice(
        [0, 1, 2, 3, 5, 7, 10, 14, 21, 30, 45, 60],
        size=n_records,
        p=[0.35, 0.10, 0.08, 0.07, 0.07, 0.07, 0.06, 0.06, 0.04, 0.04, 0.03, 0.03],
    )
    appointment = scheduled_day + pd.to_timedelta(gap, unit="D")

    # AppointmentDay carries a midnight timestamp (as in the Kaggle file), so
    # a same-day booking must be scheduled at 00:00 to survive the
    # ScheduledDay <= AppointmentDay cleaning rule. Later bookings keep a
    # realistic clinic time-of-day.
    clock = np.where(gap == 0, 0, rng.integers(7 * 3600, 20 * 3600, size=n_records))
    scheduled = scheduled_day + pd.to_timedelta(clock, unit="s")

    # Clinics do not run on Sundays: push to Monday, and keep the scheduled
    # timestamp no later than the appointment day.
    appointment = pd.DatetimeIndex(appointment)
    sunday = np.asarray(appointment.dayofweek == 6)
    appointment = pd.DatetimeIndex(appointment + pd.to_timedelta(sunday.astype(int), unit="D"))
    gap = gap + sunday.astype(int)

    sms = np.where(gap >= 3, (rng.random(n_records) < 0.62).astype(int), 0)

    age = patient_age[idx]
    dow = appointment.dayofweek.to_numpy()

    # ----- no-show probability model -----
    p = np.full(n_records, BASE_RATE, dtype=float)
    p += 0.055 * np.log1p(gap)                 # longer wait -> more misses
    p += np.where(gap == 0, -0.06, 0.0)        # same-day rarely missed
    p -= 0.045 * sms                           # reminders help
    p += np.where(age < 18, 0.045, 0.0)        # young patients miss more
    p += np.where((age >= 18) & (age < 35), 0.030, 0.0)
    p -= np.where(age >= 60, 0.045, 0.0)       # older patients attend
    p += 0.035 * scholarship[idx]
    p += 0.030 * alcoholism[idx]
    p -= 0.015 * hypertension[idx]
    p -= 0.010 * diabetes[idx]
    p += np.where(dow == 0, 0.020, 0.0)        # Monday
    p += np.where(dow == 5, 0.035, 0.0)        # Saturday
    p += (1.0 - reliability[idx]) * 0.16       # personal habit
    p += rng.normal(0, 0.02, size=n_records)   # irreducible noise

    p = np.clip(p, 0.01, 0.95)
    no_show = np.where(rng.random(n_records) < p, "Yes", "No")

    df = pd.DataFrame({
        "PatientId": patient_ids[idx].astype("float64"),
        "AppointmentID": np.arange(5_000_000, 5_000_000 + n_records),
        "Gender": patient_gender[idx],
        "ScheduledDay": scheduled.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "AppointmentDay": appointment.strftime("%Y-%m-%dT00:00:00Z"),
        "Age": age,
        "Neighbourhood": patient_hood[idx],
        "Scholarship": scholarship[idx],
        "Hipertension": hypertension[idx],
        "Diabetes": diabetes[idx],
        "Alcoholism": alcoholism[idx],
        "Handcap": handicap[idx],
        "SMS_received": sms,
        "No-show": no_show,
    })

    return df.sort_values("AppointmentID").reset_index(drop=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=int, default=110_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", default="data/raw/no_show.csv")
    args = parser.parse_args()

    print("=" * 70)
    print("   SYNTHETIC NO-SHOW DATASET GENERATOR")
    print("=" * 70)
    print("\n  ⚠️  Synthetic data. Metrics from it do not reflect real patients.")
    print("      Replace with the Kaggle export for meaningful evaluation.\n")

    df = generate(args.records, args.seed)

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    df.to_csv(args.output, index=False)

    rate = (df["No-show"] == "Yes").mean() * 100
    print(f"  Records generated : {len(df):,}")
    print(f"  Unique patients   : {df['PatientId'].nunique():,}")
    print(f"  No-show rate      : {rate:.1f}%")
    print(f"  Saved to          : {args.output}")
    print("\n  Next steps:")
    print("    python app/ml/preprocess_noshow.py")
    print("    python app/ml/train_noshow_model.py")
    print("=" * 70)


if __name__ == "__main__":
    main()
