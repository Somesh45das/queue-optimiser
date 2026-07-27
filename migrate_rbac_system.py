"""
Migration script for Role-Based Access Control (RBAC) system.
Updates existing admin users to super_admin role.
"""
from app import create_app, db
from app.models.user import User

app = create_app()

print("="*70)
print("RBAC SYSTEM MIGRATION")
print("="*70)

with app.app_context():
    try:
        # Update existing admin users to super_admin
        print("\n[STEP 1] Updating existing admin users...")
        admin_users = User.query.filter_by(role="admin").all()
        
        if admin_users:
            for user in admin_users:
                user.role = "super_admin"
                print(f"  → Updated {user.email} to super_admin")
            db.session.commit()
            print(f"  ✓ Updated {len(admin_users)} admin user(s) to super_admin")
        else:
            print("  ℹ No admin users found to update")
        
        # Create hospital admin user
        print("\n[STEP 2] Creating hospital admin user...")
        hospital_admin = User.query.filter_by(email="hospitaladmin@hospital.com").first()
        
        if hospital_admin:
            print("  ✓ Hospital admin already exists")
            if hospital_admin.role != "hospital_admin":
                hospital_admin.role = "hospital_admin"
                db.session.commit()
                print("  → Updated role to hospital_admin")
        else:
            hospital_admin = User(
                name="Hospital Administrator",
                email="hospitaladmin@hospital.com",
                phone="9999999999",
                role="hospital_admin",
                is_active=True,
                is_verified=True
            )
            hospital_admin.set_password("hospital123")
            db.session.add(hospital_admin)
            db.session.commit()
            print("  ✓ Created hospital admin user")
        
        # Display all users and their roles
        print("\n" + "="*70)
        print("USER ROLES SUMMARY")
        print("="*70)
        
        all_users = User.query.all()
        role_counts = {}
        
        for user in all_users:
            role = user.role
            if role not in role_counts:
                role_counts[role] = []
            role_counts[role].append(user)
        
        for role, users in sorted(role_counts.items()):
            print(f"\n{role.upper().replace('_', ' ')} ({len(users)}):")
            for user in users:
                print(f"  • {user.name} ({user.email})")
        
        # Display login credentials
        print("\n" + "="*70)
        print("LOGIN CREDENTIALS")
        print("="*70)
        
        print("\n🔴 SUPER ADMIN (Full System Access):")
        super_admins = User.query.filter_by(role="super_admin").all()
        for admin in super_admins:
            print(f"  Email:    {admin.email}")
            if admin.email == "admin@hospital.com":
                print(f"  Password: admin123")
        
        print("\n🟠 HOSPITAL ADMIN (Manage Appointments & Operations):")
        print(f"  Email:    hospitaladmin@hospital.com")
        print(f"  Password: hospital123")
        
        print("\n🔵 DOCTOR (View Schedule & Manage Own Appointments):")
        doctors = User.query.filter_by(role="doctor").all()
        for doc in doctors:
            print(f"  Email:    {doc.email}")
            if doc.email == "doctor@hospital.com":
                print(f"  Password: doctor123")
        
        print("\n🟢 PATIENT (Book & View Own Appointments):")
        patients = User.query.filter_by(role="user").limit(1).all()
        for patient in patients:
            print(f"  Email:    {patient.email}")
            if patient.email == "test@patient.com":
                print(f"  Password: test123")
        
        print("\n" + "="*70)
        print("ROLE PERMISSIONS")
        print("="*70)
        
        print("\n🔴 SUPER ADMIN:")
        print("  • Full system access")
        print("  • Manage doctors & departments")
        print("  • Manage users & roles")
        print("  • View all reports & analytics")
        print("  • System settings & logs")
        
        print("\n🟠 HOSPITAL ADMIN:")
        print("  • View dashboard & analytics")
        print("  • Manage appointments")
        print("  • Manage queue")
        print("  • View doctors & patients")
        print("  • Send notifications")
        print("  • Cannot: Add/delete doctors, change roles")
        
        print("\n🔵 DOCTOR:")
        print("  • View own schedule")
        print("  • Manage own appointments")
        print("  • View own queue")
        print("  • Call patients")
        print("  • Cannot: View other doctors' data")
        
        print("\n🟢 PATIENT:")
        print("  • Book appointments")
        print("  • View own appointments")
        print("  • Cancel own appointments")
        print("  • View own profile")
        print("  • Cannot: View other patients' data")
        
        print("\n" + "="*70)
        print("✅ MIGRATION COMPLETED SUCCESSFULLY!")
        print("="*70)
        
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        db.session.rollback()
        raise
