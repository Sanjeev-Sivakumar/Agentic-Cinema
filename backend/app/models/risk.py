from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field, computed_field
from app.models.entity import RiskLevel

class RiskCategory(str, Enum):
    TRADEMARK_INFRINGEMENT = "TRADEMARK_INFRINGEMENT"
    COPYRIGHT_INFRINGMENT = "COPYRIGHT_INFRINGMENT"
    RIGHT_OF_PUBLICITY = "RIGHT_OF_PUBLICITY"
    DEFAMATION = "DEFAMATION"
    CONTRACTUAL_BREACH = "CONTRACTUAL_BREACH"
    BRAND_SAFETY = "BRAND_SAFETY"
    UNFAIR_COMPETITION = "UNFAIR_COMPETITION"

class RiskFactor(BaseModel):
    category: RiskCategory
    description: str
    severity: str  # "LOW", "MEDIUM", "HIGH"
    weight: float = 1.0
    mitigating_factors: List[str] = Field(default_factory=list)

class RiskSignal(BaseModel):
    signal_name: str
    value: Any
    weight: float
    contribution: float
    explanation: str

    @computed_field
    @property
    def score_delta(self) -> float:
        return self.contribution

    @computed_field
    @property
    def triggered(self) -> bool:
        return bool(self.contribution != 0.0)


class RiskAssessment(BaseModel):
    risk_id: str = Field(default_factory=lambda: f"risk_{uuid.uuid4().hex[:10]}")
    entity_id: str
    production_id: str
    job_id: Optional[str] = None
    entity_name: str = ""
    risk_level: RiskLevel = RiskLevel.UNKNOWN
    risk_score: float = 0.0  # 0 to 100
    signals: List[RiskSignal] = Field(default_factory=list)
    explanation: str = ""
    confidence: float = 0.0  # 0.0 to 1.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    assessor: str = "RiskAssessmentAgent"

    # Backward compatibility attributes
    factors: List[RiskFactor] = Field(default_factory=list)
    legal_analysis: str = ""
    recommended_action: str = ""
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @computed_field
    @property
    def id(self) -> str:
        """Backward compatibility alias for risk_id"""
        return self.risk_id

    @computed_field
    @property
    def overall_risk_level(self) -> RiskLevel:
        """Backward compatibility alias for risk_level"""
        return self.risk_level
