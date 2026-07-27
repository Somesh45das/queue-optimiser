# No-Show Prediction Model Card

## Model Overview

**Model Type:** Random Forest Classifier  
**Purpose:** Predict patient no-show probability for appointment optimization  
**Training Date:** 2026-07-27  

## Performance Metrics

- **Test Accuracy:** 63.29%
- **Test ROC-AUC:** 0.7401
- **Training Accuracy:** 68.29%
- **Training ROC-AUC:** 0.8209

## Confusion Matrix

```
                 Predicted
                 Show  No-Show
Actual Show      10653   6989
Actual No-Show    1126   3337
```

## Top 10 Important Features

1. **booking_gap_days**: 0.2827
2. **is_same_day**: 0.2315
3. **Age**: 0.1210
4. **is_short_notice**: 0.0749
5. **previous_no_shows**: 0.0556
6. **appointment_count**: 0.0534
7. **day_of_week**: 0.0367
8. **age_group_encoded**: 0.0251
9. **SMS_received**: 0.0245
10. **month**: 0.0182

## Dataset

**Source:** Medical Appointment No Shows (Kaggle)  
**Records:** 110,527 appointments  
**Location:** Brazil  
**Time Period:** April-June 2016  

## Usage

```python
from app.services.noshow_predictor import NoShowPredictor

predictor = NoShowPredictor()
probability = predictor.predict_no_show(
    age=45,
    booking_gap_days=7,
    previous_no_shows=0,
    sms_received=1,
    # ... other features
)
print(f'No-show probability: {probability:.2%}')
```

## Integration

This model is integrated into:
- `SlotOptimizer`: Adjusts overbooking strategy
- `AppointmentManager`: Flags high-risk appointments
- `SMSService`: Prioritizes reminder sending

## Limitations

- Trained on Brazilian hospital data (may not generalize to other regions)
- Does not account for real-time factors (traffic, weather on appointment day)
- Requires patient history for best accuracy

## Future Improvements

- Add real-time weather data
- Include transportation distance
- Implement online learning for continuous improvement
- Add explainability (SHAP values)
