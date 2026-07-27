"""
One-time remote seeding helper.

After deploying to Vercel, run this locally with DATABASE_URL pointed at
your production Postgres. It creates tables (idempotent), seeds demo
departments/doctors, and creates the four demo user accounts.

Usage (PowerShell):
    $env:DATABASE_URL = "postgresql://..."
    venv\Scripts\python bootstrap_remote.py

Usage (bash):
    export DATABASE_URL="postgresql://..."
    venv/bin/python bootstrap_remote.py
"""
import os
import sys

if not os.environ.get("DATABASE_URL"):
    sys.exit("Set DATABASE_URL to your production Postgres connection string first.")

# Keep local schedulers off so this script exits cleanly.
os.environ.setdefault("ENABLE_CROWD_LOG_SCHEDULER", "False")
os.environ.setdefault("ENABLE_HEALTH_SCHEDULER", "False")
os.environ.setdefault("ENABLE_BACKUP_SCHEDULER", "False")

from app import create_app, db
from app.models.models import Department, Doctor
from app.models.user import User
from datetime import time

app = create_app()

with app.app_context():
    print("Creating tables...")
    db.create_all()

    if Department.query.count() == 0:
        print("Seeding demo departments and doctors...")
        from seed_data import seed
        seed()
    else:
        print(f"  Departments already present ({Department.query.count()}); skipping seed.")

    print("Creating demo user accounts...")
    demo_users = [
        ("admin@hospital.com", "admin123", "Super Admin", "super_admin", None),
        ("hospitaladmin@hospital.com", "hospital123", "Hospital Admin", "hospital_admin", None),
        ("test@patient.com", "test123", "Test Patient", "user", None),
    ]

    for email, password, name, role, _ in demo_users:
        if User.query.filter_by(email=email).first():
            print(f"  {email:35s} already exists, skipping")
            continue
        user = User(name=name, email=email, role=role, is_active=True)
        user.set_password(password)
        db.session.add(user)
        print(f"  {email:35s} created ({role})")

    doctor = Doctor.query.first()
    if doctor and not User.query.filter_by(email="doctor@hospital.com").first():
        du = User(name=f"Dr. {doctor.name}", email="doctor@hospital.com",
                  role="doctor", is_active=True, doctor_id=doctor.id)
        du.set_password("doctor123")
        db.session.add(du)
        print(f"  doctor@hospital.com                created (doctor, linked to Dr. {doctor.name})")

    db.session.commit()

print("\nBootstrap complete. Log in at your Vercel URL with the demo accounts:")
print("  admin@hospital.com          / admin123")
print("  hospitaladmin@hospital.com  / hospital123")
print("  doctor@hospital.com         / doctor123")
print("  test@patient.com            / test123")
