# RBAC System - Quick Reference Guide

## Login Credentials

| Role | Email | Password | Access Level |
|------|-------|----------|--------------|
| 🔴 Super Admin | admin@hospital.com | admin123 | Full system control |
| 🟠 Hospital Admin | hospitaladmin@hospital.com | hospital123 | Appointments & operations |
| 🔵 Doctor | doctor@hospital.com | doctor123 | Own schedule only |
| 🟢 Patient | test@patient.com | test123 | Own appointments only |

---

## Permission Matrix

| Permission | Super Admin | Hospital Admin | Doctor | Patient |
|------------|-------------|----------------|--------|---------|
| **Dashboard & Analytics** |
| View Dashboard | ✓ | ✓ | ✗ | ✗ |
| View Analytics | ✓ | ✓ | ✗ | ✗ |
| View Reports | ✓ | ✓ | ✗ | ✗ |
| **Appointments** |
| View All Appointments | ✓ | ✓ | ✗ | ✗ |
| View Own Appointments | ✗ | ✗ | ✓ | ✓ |
| Create Appointment | ✓ | ✓ | ✗ | ✓ |
| Edit Appointment | ✓ | ✓ | ✓* | ✗ |
| Delete Appointment | ✓ | ✗ | ✗ | ✗ |
| Cancel Appointment | ✓ | ✓ | ✓* | ✓* |
| **Queue Management** |
| View Queue | ✓ | ✓ | ✓* | ✗ |
| Manage Queue | ✓ | ✓ | ✗ | ✗ |
| Call Patient | ✓ | ✗ | ✓* | ✗ |
| **Doctor Management** |
| View Doctors | ✓ | ✓ | ✗ | ✗ |
| Add Doctor | ✓ | ✗ | ✗ | ✗ |
| Edit Doctor | ✓ | ✗ | ✗ | ✗ |
| Delete Doctor | ✓ | ✗ | ✗ | ✗ |
| Toggle Availability | ✓ | ✓ | ✗ | ✗ |
| **Department Management** |
| View Departments | ✓ | ✓ | ✗ | ✗ |
| Add Department | ✓ | ✗ | ✗ | ✗ |
| Edit Department | ✓ | ✗ | ✗ | ✗ |
| Delete Department | ✓ | ✗ | ✗ | ✗ |
| **User Management** |
| View Users | ✓ | ✗ | ✗ | ✗ |
| Add User | ✓ | ✗ | ✗ | ✗ |
| Edit User | ✓ | ✗ | ✗ | ✗ |
| Delete User | ✓ | ✗ | ✗ | ✗ |
| Change User Role | ✓ | ✗ | ✗ | ✗ |
| **System Settings** |
| View Settings | ✓ | ✗ | ✗ | ✗ |
| Edit Settings | ✓ | ✗ | ✗ | ✗ |
| View Logs | ✓ | ✗ | ✗ | ✗ |

*Only for own data

---

## Navigation Access

### Super Admin
```
✓ Dashboard
✓ Appointments
✓ Live Queue
✓ Doctors
✓ Manage Doctors (Management)
✓ Manage Departments (Management)
```

### Hospital Admin
```
✓ Dashboard
✓ Appointments
✓ Live Queue
✓ Doctors
✗ Management Section (Hidden)
```

### Doctor
```
✓ Dashboard
✓ My Appointments
✓ My Queue
✓ Schedule
✓ My Profile
```

### Patient
```
✓ My Dashboard
✓ Book Appointment
✓ Check Status
✓ Appointment History
```

---

## Code Examples

### Using Permission Decorators

```python
from app.services.permissions import permission_required, Permission

# Require specific permission
@permission_required(Permission.ADD_DOCTOR)
def add_doctor():
    pass

# Require multiple permissions
@permission_required(Permission.VIEW_DASHBOARD, Permission.EDIT_APPOINTMENT)
def manage_appointments():
    pass

# Require super admin
from app.services.permissions import super_admin_required

@super_admin_required
def system_settings():
    pass

# Require any admin
from app.services.permissions import any_admin_required

@any_admin_required
def admin_dashboard():
    pass
```

### Checking Permissions in Code

```python
from app.services.permissions import PermissionChecker, Permission
from flask_login import current_user

# Check single permission
if PermissionChecker.has_permission(current_user, Permission.ADD_DOCTOR):
    # Show add doctor button

# Check in template
{% if current_user.is_super_admin() %}
    <button>Add Doctor</button>
{% endif %}
```

---

## Testing

### Test All Roles

1. **Super Admin**
   ```bash
   # Login: admin@hospital.com / admin123
   # Test: Access all pages, add/edit/delete doctors
   ```

2. **Hospital Admin**
   ```bash
   # Login: hospitaladmin@hospital.com / hospital123
   # Test: Manage appointments, cannot access management section
   ```

3. **Doctor**
   ```bash
   # Login: doctor@hospital.com / doctor123
   # Test: View own schedule, cannot access admin pages
   ```

4. **Patient**
   ```bash
   # Login: test@patient.com / test123
   # Test: Book appointments, cannot access admin pages
   ```

---

## Migration

```bash
# Run migration to update roles
python migrate_rbac_system.py

# Test permissions
python test_rbac_permissions.py
```

---

## Troubleshooting

### Issue: User has wrong role
**Solution:** Update in database or run migration script

### Issue: Permission denied
**Solution:** Check user role and required permissions

### Issue: Navigation not showing
**Solution:** Clear browser cache and refresh

### Issue: Cannot access admin pages
**Solution:** Verify user has admin role (super_admin or hospital_admin)

---

## Summary

- ✅ 4 distinct roles with appropriate permissions
- ✅ 33 granular permissions
- ✅ Secure route protection
- ✅ Role-based navigation
- ✅ Data isolation
- ✅ Easy to test and verify

The RBAC system ensures every user has appropriate access based on their role!
