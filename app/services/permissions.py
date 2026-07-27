"""
Role-Based Access Control (RBAC) permissions system.
Defines granular permissions for each role.
"""
from enum import Enum
from functools import wraps
from flask import flash, redirect, url_for, abort
from flask_login import current_user


class Permission(Enum):
    """System permissions."""
    # Dashboard & Analytics
    VIEW_DASHBOARD = "view_dashboard"
    VIEW_ANALYTICS = "view_analytics"
    VIEW_REPORTS = "view_reports"
    
    # Appointment Management
    VIEW_ALL_APPOINTMENTS = "view_all_appointments"
    VIEW_OWN_APPOINTMENTS = "view_own_appointments"
    CREATE_APPOINTMENT = "create_appointment"
    EDIT_APPOINTMENT = "edit_appointment"
    DELETE_APPOINTMENT = "delete_appointment"
    CANCEL_APPOINTMENT = "cancel_appointment"
    
    # Queue Management
    VIEW_QUEUE = "view_queue"
    MANAGE_QUEUE = "manage_queue"
    CALL_PATIENT = "call_patient"
    
    # Doctor Management
    VIEW_DOCTORS = "view_doctors"
    ADD_DOCTOR = "add_doctor"
    EDIT_DOCTOR = "edit_doctor"
    DELETE_DOCTOR = "delete_doctor"
    TOGGLE_DOCTOR_AVAILABILITY = "toggle_doctor_availability"
    
    # Department Management
    VIEW_DEPARTMENTS = "view_departments"
    ADD_DEPARTMENT = "add_department"
    EDIT_DEPARTMENT = "edit_department"
    DELETE_DEPARTMENT = "delete_department"
    
    # Patient Management
    VIEW_ALL_PATIENTS = "view_all_patients"
    VIEW_OWN_PROFILE = "view_own_profile"
    EDIT_PATIENT = "edit_patient"
    DELETE_PATIENT = "delete_patient"
    
    # User Management
    VIEW_USERS = "view_users"
    ADD_USER = "add_user"
    EDIT_USER = "edit_user"
    DELETE_USER = "delete_user"
    CHANGE_USER_ROLE = "change_user_role"
    
    # Notification Management
    SEND_NOTIFICATIONS = "send_notifications"
    VIEW_NOTIFICATIONS = "view_notifications"
    
    # System Settings
    VIEW_SETTINGS = "view_settings"
    EDIT_SETTINGS = "edit_settings"
    VIEW_LOGS = "view_logs"


# Role-Permission Mapping
ROLE_PERMISSIONS = {
    "super_admin": [
        # Full system access - all permissions
        Permission.VIEW_DASHBOARD,
        Permission.VIEW_ANALYTICS,
        Permission.VIEW_REPORTS,
        Permission.VIEW_ALL_APPOINTMENTS,
        Permission.CREATE_APPOINTMENT,
        Permission.EDIT_APPOINTMENT,
        Permission.DELETE_APPOINTMENT,
        Permission.CANCEL_APPOINTMENT,
        Permission.VIEW_QUEUE,
        Permission.MANAGE_QUEUE,
        Permission.CALL_PATIENT,
        Permission.VIEW_DOCTORS,
        Permission.ADD_DOCTOR,
        Permission.EDIT_DOCTOR,
        Permission.DELETE_DOCTOR,
        Permission.TOGGLE_DOCTOR_AVAILABILITY,
        Permission.VIEW_DEPARTMENTS,
        Permission.ADD_DEPARTMENT,
        Permission.EDIT_DEPARTMENT,
        Permission.DELETE_DEPARTMENT,
        Permission.VIEW_ALL_PATIENTS,
        Permission.EDIT_PATIENT,
        Permission.DELETE_PATIENT,
        Permission.VIEW_USERS,
        Permission.ADD_USER,
        Permission.EDIT_USER,
        Permission.DELETE_USER,
        Permission.CHANGE_USER_ROLE,
        Permission.SEND_NOTIFICATIONS,
        Permission.VIEW_NOTIFICATIONS,
        Permission.VIEW_SETTINGS,
        Permission.EDIT_SETTINGS,
        Permission.VIEW_LOGS,
    ],
    
    "hospital_admin": [
        # Manage appointments and operations
        Permission.VIEW_DASHBOARD,
        Permission.VIEW_ANALYTICS,
        Permission.VIEW_REPORTS,
        Permission.VIEW_ALL_APPOINTMENTS,
        Permission.CREATE_APPOINTMENT,
        Permission.EDIT_APPOINTMENT,
        Permission.CANCEL_APPOINTMENT,
        Permission.VIEW_QUEUE,
        Permission.MANAGE_QUEUE,
        Permission.VIEW_DOCTORS,
        Permission.TOGGLE_DOCTOR_AVAILABILITY,
        Permission.VIEW_DEPARTMENTS,
        Permission.VIEW_ALL_PATIENTS,
        Permission.EDIT_PATIENT,
        Permission.SEND_NOTIFICATIONS,
        Permission.VIEW_NOTIFICATIONS,
    ],
    
    "doctor": [
        # View schedule and manage own appointments
        Permission.VIEW_OWN_APPOINTMENTS,
        Permission.EDIT_APPOINTMENT,  # Only own appointments
        Permission.CANCEL_APPOINTMENT,  # Only own appointments
        Permission.VIEW_QUEUE,  # Only own queue
        Permission.CALL_PATIENT,  # Only own patients
        Permission.VIEW_OWN_PROFILE,
    ],
    
    "user": [
        # Patient - book and view own appointments
        Permission.VIEW_OWN_APPOINTMENTS,
        Permission.CREATE_APPOINTMENT,
        Permission.CANCEL_APPOINTMENT,  # Only own appointments
        Permission.VIEW_OWN_PROFILE,
    ],
}


class PermissionChecker:
    """Check user permissions."""
    
    @staticmethod
    def has_permission(user, permission: Permission) -> bool:
        """Check if user has a specific permission."""
        if not user or not user.is_authenticated:
            return False
        
        role = user.role
        if role not in ROLE_PERMISSIONS:
            return False
        
        return permission in ROLE_PERMISSIONS[role]
    
    @staticmethod
    def has_any_permission(user, permissions: list) -> bool:
        """Check if user has any of the specified permissions."""
        return any(PermissionChecker.has_permission(user, perm) for perm in permissions)
    
    @staticmethod
    def has_all_permissions(user, permissions: list) -> bool:
        """Check if user has all of the specified permissions."""
        return all(PermissionChecker.has_permission(user, perm) for perm in permissions)
    
    @staticmethod
    def get_user_permissions(user) -> list:
        """Get all permissions for a user."""
        if not user or not user.is_authenticated:
            return []
        
        role = user.role
        return ROLE_PERMISSIONS.get(role, [])


def permission_required(*permissions):
    """
    Decorator to require specific permissions.
    Usage: @permission_required(Permission.VIEW_DASHBOARD, Permission.EDIT_APPOINTMENT)
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Please login to access this page.', 'warning')
                return redirect(url_for('auth.login'))
            
            # Check if user has all required permissions
            for permission in permissions:
                if not PermissionChecker.has_permission(current_user, permission):
                    flash('Access denied. You do not have permission to access this resource.', 'danger')
                    # Redirect based on role
                    if current_user.is_doctor():
                        return redirect(url_for('doctor_portal.dashboard'))
                    elif current_user.is_admin():
                        return redirect(url_for('dashboard.index'))
                    else:
                        return redirect(url_for('patient_portal.dashboard'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def super_admin_required(f):
    """Decorator to require super admin role."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please login to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        
        if not current_user.is_super_admin():
            flash('Access denied. Super admin privileges required.', 'danger')
            abort(403)
        
        return f(*args, **kwargs)
    return decorated_function


def hospital_admin_required(f):
    """Decorator to require hospital admin or super admin role."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please login to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        
        if not (current_user.is_hospital_admin() or current_user.is_super_admin()):
            flash('Access denied. Admin privileges required.', 'danger')
            abort(403)
        
        return f(*args, **kwargs)
    return decorated_function


def any_admin_required(f):
    """Decorator to require any admin role (super or hospital)."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please login to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        
        if not current_user.is_admin():
            flash('Access denied. Admin privileges required.', 'danger')
            if current_user.is_doctor():
                return redirect(url_for('doctor_portal.dashboard'))
            else:
                return redirect(url_for('patient_portal.dashboard'))
        
        return f(*args, **kwargs)
    return decorated_function
