"""
Department capacity monitoring.

Implements Requirement 19: track live occupancy, expose warning/alert
thresholds, block bookings at capacity and suggest alternatives.
"""
from datetime import date

from app.models.models import Department, QueueEntry

WARNING_THRESHOLD = 80.0   # Requirement 19.2
ALERT_THRESHOLD = 100.0    # Requirement 19.3

ACTIVE_STATUSES = ("waiting", "in_progress")


class CapacityManager:
    """Computes department occupancy from live queue state."""

    @staticmethod
    def current_count(department_id: int, target_date: date = None) -> int:
        """Requirement 19.1: patients currently waiting or in progress."""
        target_date = target_date or date.today()
        return QueueEntry.query.filter(
            QueueEntry.department_id == department_id,
            QueueEntry.queue_date == target_date,
            QueueEntry.status.in_(ACTIVE_STATUSES),
        ).count()

    @classmethod
    def get_status(cls, department, target_date: date = None) -> dict:
        """
        Build a capacity summary for one department.

        Requirement 19.6: capacity_percentage = (current / max) * 100.
        """
        if isinstance(department, int):
            department = Department.query.get(department)
        if department is None:
            return {
                "department_id": None,
                "name": "Unknown",
                "current_count": 0,
                "max_capacity": 0,
                "capacity_percentage": 0.0,
                "state": "normal",
                "color": "#28a745",
                "label": "Normal",
                "is_full": False,
            }

        current = cls.current_count(department.id, target_date)
        maximum = department.max_capacity or 0
        percentage = round((current / maximum) * 100, 1) if maximum else 0.0

        if percentage >= ALERT_THRESHOLD:
            state, color, label = "alert", "#dc3545", "At capacity"
        elif percentage >= WARNING_THRESHOLD:
            state, color, label = "warning", "#ffc107", "Near capacity"
        else:
            state, color, label = "normal", "#28a745", "Normal"

        return {
            "department_id": department.id,
            "name": department.name,
            "current_count": current,
            "max_capacity": maximum,
            "capacity_percentage": percentage,
            "state": state,
            "color": color,
            "label": label,
            "is_full": bool(maximum) and current >= maximum,
        }

    @classmethod
    def all_statuses(cls, target_date: date = None) -> list:
        """Capacity summary for every active department (Requirement 19.7)."""
        departments = Department.query.filter_by(is_active=True).order_by(
            Department.name
        ).all()
        return [cls.get_status(dept, target_date) for dept in departments]

    @classmethod
    def is_bookable(cls, department_id: int, target_date: date = None) -> bool:
        """Requirement 19.4: block new bookings when a department is full."""
        return not cls.get_status(department_id, target_date)["is_full"]

    @classmethod
    def suggest_alternatives(cls, department_id: int, limit: int = 3,
                             target_date: date = None) -> list:
        """
        Requirement 19.5: suggest alternative departments with free capacity,
        ordered by lowest utilisation first.
        """
        options = [
            status for status in cls.all_statuses(target_date)
            if status["department_id"] != department_id and not status["is_full"]
        ]
        options.sort(key=lambda item: item["capacity_percentage"])
        return options[:limit]
