"""
ML-based crowd level prediction service.
Uses historical data to predict OPD crowd levels.
"""
import os
from datetime import datetime, date
from config import Config

# Try to import ML libraries, but don't fail if they're not available
try:
    import numpy as np
    import joblib
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    print("[CrowdPredictor] ML libraries not available - using fallback mode")


class CrowdPredictor:
    """Predicts crowd levels using a trained ML model."""

    CROWD_LEVELS = {0: "low", 1: "medium", 2: "high", 3: "critical"}
    CROWD_COLORS = {
        "low": "#28a745",
        "medium": "#ffc107",
        "high": "#fd7e14",
        "critical": "#dc3545",
    }

    # Process-wide cache so the model/scaler are deserialized only once.
    # Requirement 1.4 / 21.1: predictions must complete within 50 ms.
    _cached_model = None
    _cached_scaler = None
    _load_attempted = False

    # Memoized predictions: identical department/date/hour lookups recur
    # constantly (dashboard timelines, slot scoring for a whole day).
    _prediction_cache = {}
    _CACHE_LIMIT = 4096

    def __init__(self):
        self._load_model()

    @property
    def model(self):
        return CrowdPredictor._cached_model

    @model.setter
    def model(self, value):
        CrowdPredictor._cached_model = value

    @property
    def scaler(self):
        return CrowdPredictor._cached_scaler

    @scaler.setter
    def scaler(self, value):
        CrowdPredictor._cached_scaler = value

    @classmethod
    def reload_model(cls):
        """Force the cached model to be re-read from disk on next use."""
        cls._cached_model = None
        cls._cached_scaler = None
        cls._load_attempted = False
        cls._prediction_cache = {}

    def _load_model(self):
        """Load the trained model and scaler from disk (once per process)."""
        if CrowdPredictor._load_attempted:
            return

        CrowdPredictor._load_attempted = True

        if not ML_AVAILABLE:
            print("[CrowdPredictor] ML libraries not available - using fallback")
            CrowdPredictor._cached_model = None
            return

        try:
            if os.path.exists(Config.ML_MODEL_PATH) and os.path.exists(Config.ML_SCALER_PATH):
                # Requirement 3.6: verify model file integrity before use.
                model = joblib.load(Config.ML_MODEL_PATH)
                scaler = joblib.load(Config.ML_SCALER_PATH)
                if not hasattr(model, "predict_proba"):
                    raise ValueError("Loaded object is not a fitted classifier")

                # The model was trained with n_jobs=-1. For the single-row
                # predictions this service makes, joblib's thread dispatch
                # dominates runtime (~73 ms vs ~9 ms). Force serial execution
                # to satisfy the 50 ms budget in Requirement 1.4 / 21.1.
                try:
                    model.n_jobs = 1
                except AttributeError:
                    pass

                CrowdPredictor._cached_model = model
                CrowdPredictor._cached_scaler = scaler
            else:
                print("[CrowdPredictor] Model files not found - using rule-based fallback")
        except Exception as e:
            # Requirement 3.7: log the error and activate fallback mode.
            print(f"[CrowdPredictor] Model not loaded ({e}) - using rule-based fallback")
            CrowdPredictor._cached_model = None
            CrowdPredictor._cached_scaler = None

    def _build_features(
        self,
        department_id: int,
        target_date: date,
        hour: int,
        is_holiday: bool = False,
        temperature: float = 25.0,
        current_count: int = 0,
    ):
        """Build feature vector for prediction."""
        if not ML_AVAILABLE:
            return None
            
        day_of_week = target_date.weekday()
        month = target_date.month
        is_weekend = 1 if day_of_week >= 5 else 0
        is_monday = 1 if day_of_week == 0 else 0

        # Peak hour indicators
        is_morning_peak = 1 if 9 <= hour <= 11 else 0
        is_afternoon_peak = 1 if 14 <= hour <= 16 else 0

        # Seasonal indicator (flu season: Nov-Feb)
        is_flu_season = 1 if month in [11, 12, 1, 2] else 0

        features = np.array(
            [
                [
                    department_id,
                    hour,
                    day_of_week,
                    month,
                    int(is_holiday),
                    is_weekend,
                    is_monday,
                    is_morning_peak,
                    is_afternoon_peak,
                    is_flu_season,
                    temperature,
                    current_count,
                ]
            ]
        )
        return features

    def predict_crowd_level(
        self,
        department_id: int,
        target_date: date = None,
        hour: int = None,
        is_holiday: bool = False,
        temperature: float = 25.0,
        current_count: int = 0,
    ) -> dict:
        """
        Predict crowd level for a given department, date, and hour.

        Returns dict with level, confidence, color, patient_estimate.
        """
        if target_date is None:
            target_date = date.today()
        if hour is None:
            hour = datetime.now().hour

        # Fallback if model not loaded (e.g., in serverless environment)
        if self.model is None:
            return self._fallback_prediction(hour, current_count)

        features = self._build_features(
            department_id, target_date, hour, is_holiday, temperature, current_count
        )

        # If model is available, use it
        if self.model is not None and self.scaler is not None:
            cache_key = (
                department_id, target_date.toordinal(), hour,
                bool(is_holiday), round(float(temperature), 1), int(current_count),
            )
            cached = CrowdPredictor._prediction_cache.get(cache_key)
            if cached is not None:
                prediction, confidence = cached
            else:
                scaled = self.scaler.transform(features)
                # One traversal only: derive the class from the probabilities
                # instead of calling predict() and predict_proba() separately.
                probabilities = self.model.predict_proba(scaled)[0]
                best_index = int(np.argmax(probabilities))
                prediction = int(self.model.classes_[best_index])
                confidence = float(probabilities[best_index]) * 100

                if len(CrowdPredictor._prediction_cache) >= self._CACHE_LIMIT:
                    CrowdPredictor._prediction_cache.clear()
                CrowdPredictor._prediction_cache[cache_key] = (prediction, confidence)
        else:
            # Fallback: rule-based prediction
            prediction, confidence = self._rule_based_predict(
                hour, target_date.weekday(), current_count
            )

        level = self.CROWD_LEVELS.get(prediction, "medium")
        patient_estimate = self._estimate_patient_count(level, hour)

        return {
            "level": level,
            "level_code": int(prediction),
            "confidence": round(confidence, 1),
            "color": self.CROWD_COLORS[level],
            "patient_estimate": patient_estimate,
            "hour": hour,
            "date": target_date.isoformat(),
            "department_id": department_id,
        }

    def _rule_based_predict(self, hour: int, day_of_week: int, current_count: int):
        """Fallback rule-based prediction when ML model is unavailable."""
        score = 0

        # Time-based scoring
        if 9 <= hour <= 11:
            score += 3
        elif 14 <= hour <= 16:
            score += 2
        elif 8 <= hour <= 12:
            score += 1

        # Day-based scoring
        if day_of_week == 0:  # Monday
            score += 2
        elif day_of_week in [1, 2]:
            score += 1
        elif day_of_week >= 5:  # Weekend
            score -= 1

        # Current load
        if current_count > 30:
            score += 2
        elif current_count > 15:
            score += 1

        # Map to levels
        if score >= 5:
            return 3, 70.0  # critical
        elif score >= 3:
            return 2, 65.0  # high
        elif score >= 1:
            return 1, 60.0  # medium
        else:
            return 0, 75.0  # low

    def _fallback_prediction(self, hour: int, current_count: int) -> dict:
        """Simple fallback when ML model is not available."""
        day_of_week = datetime.now().weekday()
        prediction, confidence = self._rule_based_predict(hour, day_of_week, current_count)
        level = self.CROWD_LEVELS.get(prediction, "medium")
        patient_estimate = self._estimate_patient_count(level, hour)
        
        return {
            "level": level,
            "level_code": int(prediction),
            "confidence": round(confidence, 1),
            "color": self.CROWD_COLORS[level],
            "patient_estimate": patient_estimate,
            "hour": hour,
            "date": date.today().isoformat(),
            "department_id": 0,
            "note": "Using rule-based prediction (ML model not available)"
        }

    def _estimate_patient_count(self, level: str, hour: int) -> int:
        """Estimate patient count based on crowd level."""
        base = {"low": 8, "medium": 20, "high": 35, "critical": 50}
        count = base.get(level, 15)

        # Adjust for hour
        if 9 <= hour <= 11:
            count = int(count * 1.3)
        elif hour < 9 or hour > 17:
            count = int(count * 0.5)

        return count

    def predict_day_timeline(
        self, department_id: int, target_date: date = None
    ) -> list:
        """Predict crowd levels for every hour of OPD operation."""
        if target_date is None:
            target_date = date.today()

        timeline = []
        for hour in range(Config.OPD_START_HOUR, Config.OPD_END_HOUR + 1):
            pred = self.predict_crowd_level(department_id, target_date, hour)
            pred["time_label"] = f"{hour:02d}:00"
            timeline.append(pred)

        return timeline
