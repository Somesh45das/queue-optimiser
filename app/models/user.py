"""
User authentication models with role-based access control.
"""
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db

# Requirement 22.4: bcrypt with a minimum of 12 rounds.
BCRYPT_ROUNDS = 12

try:
    import bcrypt as _bcrypt
    _BCRYPT_AVAILABLE = True
except ImportError:  # pragma: no cover - bcrypt ships with flask-bcrypt
    _bcrypt = None
    _BCRYPT_AVAILABLE = False
    print("[User] bcrypt unavailable - falling back to PBKDF2 password hashing")


class User(UserMixin, db.Model):
    """User model for authentication and authorization."""
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(15), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="user")  # user, super_admin, hospital_admin, doctor
    is_active = db.Column(db.Boolean, default=True)
    is_verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    
    # Relationship to patient records
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id"), nullable=True)
    patient = db.relationship("Patient", backref="user_account", uselist=False)
    
    # Relationship to doctor records
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctors.id"), nullable=True)
    doctor = db.relationship("Doctor", backref="user_account", uselist=False)

    def __repr__(self):
        return f"<User {self.email} - {self.role}>"

    def set_password(self, password):
        """
        Hash and set password.

        Requirement 22.4: passwords are hashed with bcrypt using at least
        12 rounds. Falls back to PBKDF2 only if bcrypt is unavailable.
        """
        if _BCRYPT_AVAILABLE:
            self.password_hash = _bcrypt.hashpw(
                password.encode("utf-8"), _bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
            ).decode("utf-8")
        else:
            self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """
        Verify password against the stored hash.

        Supports both bcrypt hashes and legacy Werkzeug hashes so existing
        accounts keep working; legacy hashes are upgraded transparently.
        """
        stored = self.password_hash or ""

        if stored.startswith(("$2a$", "$2b$", "$2y$")):
            if not _BCRYPT_AVAILABLE:
                return False
            try:
                return _bcrypt.checkpw(password.encode("utf-8"), stored.encode("utf-8"))
            except (ValueError, TypeError):
                return False

        # Legacy Werkzeug hash: verify, then transparently upgrade to bcrypt.
        try:
            is_valid = check_password_hash(stored, password)
        except (ValueError, TypeError):
            return False

        if is_valid and _BCRYPT_AVAILABLE:
            self.set_password(password)
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()

        return is_valid

    def is_admin(self):
        """Check if user has any admin role."""
        return self.role in ["super_admin", "hospital_admin"]
    
    def is_super_admin(self):
        """Check if user has super admin role."""
        return self.role == "super_admin"
    
    def is_hospital_admin(self):
        """Check if user has hospital admin role."""
        return self.role == "hospital_admin"

    def is_user(self):
        """Check if user has user/patient role."""
        return self.role == "user"
    
    def is_doctor(self):
        """Check if user has doctor role."""
        return self.role == "doctor"

    def update_last_login(self):
        """Update last login timestamp."""
        self.last_login = datetime.utcnow()
        db.session.commit()


class LoginAttempt(db.Model):
    """
    Audit trail of authentication attempts.

    Requirement 22.7: log all authentication attempts with username,
    timestamp, ip_address and success_status.
    """
    __tablename__ = "login_attempts"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), nullable=False, index=True)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    success = db.Column(db.Boolean, default=False, nullable=False)
    reason = db.Column(db.String(120), nullable=True)
    attempted_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        state = "SUCCESS" if self.success else "FAILURE"
        return f"<LoginAttempt {self.username} {state} @ {self.attempted_at}>"


class PasswordResetToken(db.Model):
    """Password reset tokens for forgot password functionality."""
    __tablename__ = "password_reset_tokens"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    token = db.Column(db.String(255), unique=True, nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="reset_tokens")

    def __repr__(self):
        return f"<PasswordResetToken {self.token[:10]}... for user {self.user_id}>"

    def is_valid(self):
        """Check if token is still valid."""
        return not self.used and datetime.utcnow() < self.expires_at
