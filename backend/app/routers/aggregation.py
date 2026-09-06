from fastapi import APIRouter
from app.schemas.aggregation import AggregateRequestSchema, FinalAssessmentAggregationSchema
from app.services.aggregation_service import aggregate_final_assessment

router = APIRouter(
    prefix="/assessment",
    tags=["Assessment"]
)

@router.post("/aggregate", response_model=FinalAssessmentAggregationSchema)
def aggregate_candidate_assessment(payload: AggregateRequestSchema):
    """
    Aggregates multiple individual skill assessment results into one final candidate-level result.
    """
    return aggregate_final_assessment(payload.skills)
