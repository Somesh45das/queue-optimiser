"""
Test script to verify RBAC permissions are working correctly.
"""
from app import create_app
from app.models.user import User
from app.services.permissions import PermissionChecker, Permission

app = create_app()

with app.app_context():
    print("="*70)
    print("RBAC PERMISSION TESTING")
    print("="*70)
    
    # Get users
    super_admin = User.query.filter_by(email="admin@hospital.com").first()
    hospital_admin = User.query.filter_by(email="hospitaladmin@hospital.com").first()
    doctor = User.query.filter_by(email="doctor@hospital.com").first()
    patient = User.query.filter_by(email="test@patient.com").first()
    
    users = [
        ("Super Admin", super_admin),
        ("Hospital Admin", hospital_admin),
        ("Doctor", doctor),
        ("Patient", patient)
    ]
    
    # Test permissions
    test_permissions = [
        ("Add Doctor", Permission.ADD_DOCTOR),
        ("Edit Doctor", Permission.EDIT_DOCTOR),
        ("Delete Doctor", Permission.DELETE_DOCTOR),
        ("View Dashboard", Permission.VIEW_DASHBOARD),
        ("Manage Queue", Permission.MANAGE_QUEUE),
        ("View All Appointments", Permission.VIEW_ALL_APPOINTMENTS),
        ("View Own Appointments", Permission.VIEW_OWN_APPOINTMENTS),
        ("Create Appointment", Permission.CREATE_APPOINTMENT),
        ("Edit Settings", Permission.EDIT_SETTINGS),
        ("Change User Role", Permission.CHANGE_USER_ROLE),
    ]
    
    # Create permission matrix
    print("\nPERMISSION MATRIX:")
    print("-"*70)
    
    # Header
    print(f"{'Permission':<30} {'Super':<8} {'Hospital':<10} {'Doctor':<8} {'Patient':<8}")
    print("-"*70)
    
    for perm_name, permission in test_permissions:
        row = f"{perm_name:<30}"
        for user_name, user in users:
            if user:
                has_perm = PermissionChecker.has_permission(user, permission)
                row += f" {'✓':<8}" if has_perm else f" {'✗':<8}"
            else:
                row += f" {'N/A':<8}"
        print(row)
    
    print("\n" + "="*70)
    print("ROLE VERIFICATION")
    print("="*70)
    
    for user_name, user in users:
        if user:
            print(f"\n{user_name} ({user.email}):")
            print(f"  Role: {user.role}")
            print(f"  is_admin(): {user.is_admin()}")
            print(f"  is_super_admin(): {user.is_super_admin()}")
            print(f"  is_hospital_admin(): {user.is_hospital_admin()}")
            print(f"  is_doctor(): {user.is_doctor()}")
            print(f"  is_user(): {user.is_user()}")
            
            permissions = PermissionChecker.get_user_permissions(user)
            print(f"  Total Permissions: {len(permissions)}")
    
    print("\n" + "="*70)
    print("✅ PERMISSION TESTING COMPLETED")
    print("="*70)
