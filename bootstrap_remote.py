"""
One-shot remote database seeder for production deployments.

Creates schema, seeds departments/doctors/demo patients/demo appointments,
and creates the four demo user accounts with the correct role values.

Idempotent: re-running only inserts what's missing.

Usage (PowerShell):
    $env:DATABASE_URL = "postgresql://..."
    venv\Scripts\python bootstrap_remote.py

Usage (bash):
    export DATABASE_URL="postgresql://..."
    venv/bin/python bootstrap_remote.py
"""
import os
import random
import sys
import time
from datetime import date, datetime, time as dtime, timedelta

if not os.environ.get("DATABASE_URL"):
    sys.exit("Set DATABASE_URL to your production Postgres connection string first.")

# Keep local schedulers off so this script exits cleanly.
os.environ.setdefault("ENABLE_CROWD_LOG_SCHEDULER", "False")
os.environ.setdefault("ENABLE_HEALTH_SCHEDULER", "False")
os.environ.setdefault("ENABLE_BACKUP_SCHEDULER", "False")

from app import create_app, db  # noqa: E402
from app.models.models import Appointment, Department, Doctor, Notification, Patient  # noqa: E402
from app.models.user import User  # noqa: E402


DEPARTMENTS = [
    # name, floor, max_capacity, avg_consultation_min
    ("General Medicine", 1, 60, 12),
    ("Pediatrics",       1, 40, 15),
    ("Orthopedics",      2, 35, 20),
    ("Cardiology",       2, 30, 18),
    ("Dermatology",      3, 25, 10),
    ("ENT",              3, 30, 12),
]

# (name, specialization, department_index_1based, experience_years,
#  avg_consultation, max_per_day, shift_start_hour, shift_end_hour, rating)
DOCTORS = [
    ("Aisha Sharma",  "General Physician",  1, 12, 12, 40, 8, 16, 4.5),
    ("Rajesh Patel",  "General Physician",  1,  8, 15, 35, 9, 17, 4.2),
    ("Priya Mehta",   "Internal Medicine",  1, 15, 10, 45, 8, 14, 4.8),
    ("Vikram Singh",  "Pediatrician",       2, 10, 15, 30, 8, 16, 4.6),
    ("Sunita Reddy",  "Child Specialist",   2,  6, 18, 25, 10, 18, 4.3),
    ("Deepak Gupta",  "Orthopedic Surgeon", 3, 20, 20, 25, 9, 17, 4.7),
    ("Neha Kapoor",   "Orthopedist",        3,  7, 15, 30, 8, 15, 4.1),
    ("Amit Joshi",    "Cardiologist",       4, 18, 20, 20, 9, 17, 4.9),
    ("Kavita Nair",   "Heart Specialist",   4, 12, 18, 22, 10, 18, 4.4),
    ("Rahul Verma",   "Dermatologist",      5,  9, 10, 35, 8, 16, 4.3),
    ("Meera Das",     "Skin Specialist",    5,  5, 12, 30, 9, 17, 4.0),
    ("Suresh Kumar",  "ENT Specialist",     6, 14, 12, 30, 8, 16, 4.5),
]

# email, password, name, role, phone
DEMO_USERS = [
    ("admin@hospital.com",         "admin123",    "Super Admin",    "super_admin",    "+91-9999999999"),
    ("hospitaladmin@hospital.com", "hospital123", "Hospital Admin", "hospital_admin", "+91-9999999998"),
    ("test@patient.com",           "test123",     "Test Patient",   "user",           "+91-8888888888"),
]


def seed():
    started = time.perf_counter()
    print("Creating schema...")
    db.create_all()

    inserted = {"departments": 0, "doctors": 0, "users": 0, "patients": 0}

    print("Seeding departments...")
    depts_by_name = {d.name: d for d in Department.query.all()}
    for name, floor, cap, avg_time in DEPARTMENTS:
        if name in depts_by_name:
            continue
        dept = Department(name=name, floor=floor,
                          max_capacity=cap, avg_consultation_min=avg_time)
        db.session.add(dept)
        depts_by_name[name] = dept
        inserted["departments"] += 1

    # Flush once so departments get IDs for the doctors.
    if inserted["departments"]:
        db.session.flush()

    print("Seeding doctors...")
    existing_docs = {d.name for d in Doctor.query.all()}
    dept_list = list(depts_by_name.values())
    for name, spec, dept_idx, exp, avg, max_p, s_start, s_end, rating in DOCTORS:
        if name in existing_docs:
            continue
        dept = dept_list[(dept_idx - 1) % len(dept_list)]
        db.session.add(Doctor(
            name=name, specialization=spec, department_id=dept.id,
            experience_years=exp, avg_consultation_min=avg,
            max_patients_per_day=max_p,
            shift_start=dtime(s_start, 0), shift_end=dtime(s_end, 0),
            rating=rating,
        ))
        inserted["doctors"] += 1
    if inserted["doctors"]:
        db.session.flush()

    print("Seeding patient profile for the demo patient user...")
    test_patient = Patient.query.filter_by(email="test@patient.com").first()
    if not test_patient:
        test_patient = Patient(
            patient_id=f"P-{date.today().strftime('%Y%m%d')}-999",
            name="Test Patient", age=30, gender="Male",
            phone="+91-8888888888", email="test@patient.com",
        )
        db.session.add(test_patient)
        db.session.flush()
        inserted["patients"] += 1

    print("Seeding demo user accounts...")
    for email, password, name, role, phone in DEMO_USERS:
        if User.query.filter_by(email=email).first():
            continue
        user = User(name=name, email=email, phone=phone, role=role, is_active=True)
        user.set_password(password)
        if role == "user":
            user.patient_id = test_patient.id
        db.session.add(user)
        inserted["users"] += 1

    # Doctor account, linked to the first doctor record.
    if not User.query.filter_by(email="doctor@hospital.com").first():
        first_doc = Doctor.query.first()
        du = User(name=f"Dr. {first_doc.name}",
                  email="doctor@hospital.com", role="doctor", is_active=True,
                  doctor_id=first_doc.id)
        du.set_password("doctor123")
        db.session.add(du)
        inserted["users"] += 1

    print("Committing...")
    db.session.commit()
    took = time.perf_counter() - started
    print(f"\n  Inserted: {inserted}")
    print(f"  Elapsed:  {took:.1f}s")


def main():
    app = create_app()
    with app.app_context():
        seed()

    print("\n  Log in at your Vercel URL with any of these accounts:")
    print("    admin@hospital.com          / admin123      (super_admin)")
    print("    hospitaladmin@hospital.com  / hospital123   (hospital_admin)")
    print("    doctor@hospital.com         / doctor123     (doctor)")
    print("    test@patient.com            / test123       (patient)")


if __name__ == "__main__":
    main()
