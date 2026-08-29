from fastapi import APIRouter, HTTPException, status

from app.schemas.ml import MLPredictRequestSchema, MLPredictResponseSchema
from app.ml.predict import SkillLevelPredictor


router = APIRouter(prefix="/ml", tags=["ML"])


@router.post("/predict", response_model=MLPredictResponseSchema)
async def predict_ml_skill_level(payload: MLPredictRequestSchema):
    """
    Accepts candidate skill feature inputs and returns the ML predicted proficiency level.
    Validates input feature bounds and types.
    """
    try:
        predictor = SkillLevelPredictor()
        feature_dict = payload.model_dump()
        result = predictor.predict_single(feature_dict)
        return MLPredictResponseSchema(predicted_level=result["predicted_level"])
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except FileNotFoundError as fnfe:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(fnfe)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Prediction failed: {str(e)}"
        )
