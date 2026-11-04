"""Pydantic schemas package for API request and response contracts."""

from .auth import (
    RegisterRequest,
    LoginRequest,
    GoogleAuthRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    UserResponse,
    TokenResponse,
    UserCreate,
)
from .requirements import (
    RequirementRequest,
    RequirementItemSchema,
    RequirementAnalysisResponse,
)
from .cv import (
    MatchedSkillSchema,
    MissingSkillSchema,
    SkillScoreSchema,
    CVAnalyzeResponseSchema,
)
from .assessment import (
    StartAssessmentRequest,
    StartAssessmentResponse,
    SubmitAnswerRequest,
    SubmitAnswerResponse,
    AttemptStatusResponse,
    CompleteAssessmentResponse,
    AssessmentHistoryObservation,
    AssessmentReviewResponse,
    TargetedRevisionResponse,
    InterviewPrepSummaryResponse,
    SkillAnalysisDetailResponse,
    PersonalizedNextStepsResponse,
)
from .aggregation import (
    AggregateRequestSchema,
    FinalAssessmentAggregationSchema,
)
from .ml import (
    MLPredictRequestSchema,
    MLPredictResponseSchema,
)
