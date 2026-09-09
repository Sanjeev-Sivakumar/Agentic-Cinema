"""
Financial Exposure Intelligence Models (Phase 10).
Quantifies potential statutory liability, commercial licensing fee benchmarks,
and remediation cost estimates for detected clearance items.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field


class FinancialExposureStatus(str, Enum):
    ESTIMATED = "ESTIMATED"
    NOT_ESTIMABLE = "NOT_ESTIMABLE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class StatutoryDamages(BaseModel):
    statutory_code: str = "17 U.S.C. § 504 / 15 U.S.C. § 1117"
    min_statutory_amount: float = 750.0
    standard_max_amount: float = 30000.0
    willful_max_amount: float = 150000.0
    statutory_basis: str = "Federal Copyright & Trademark Infringement Statutory Range"
    citation: Optional[str] = "17 U.S. Code § 504 - Remedies for infringement: Damages and profits"


class LicensingBenchmark(BaseModel):
    industry_sector: str = "Entertainment & Media (Film/Streaming)"
    low_fee: float = 2500.0
    median_fee: float = 10000.0
    high_fee: float = 35000.0
    rights_scope: str = "Worldwide, Theatrical & All Media in Perpetuity"
    source: str = "Industry Clearance & Synchronization Licensing Standards"


class RemediationCostEstimate(BaseModel):
    vfx_paintout_low: float = 1200.0
    vfx_paintout_high: float = 6500.0
    reshoot_estimated_cost: float = 25000.0
    license_settlement_low: float = 2500.0
    license_settlement_high: float = 15000.0


class ComparableCase(BaseModel):
    case_title: str
    year: int
    court_or_jurisdiction: str
    damages_or_settlement: str
    summary: str
    citation_url: Optional[str] = None


class FinancialExposure(BaseModel):
    exposure_id: str = Field(default_factory=lambda: f"exp_{uuid.uuid4().hex[:10]}")
    entity_id: str
    production_id: str
    entity_name: str
    status: FinancialExposureStatus = FinancialExposureStatus.ESTIMATED
    estimated_low: float = 0.0
    estimated_high: float = 0.0
    currency: str = "USD"
    confidence: float = 0.85
    statutory_framework: Optional[StatutoryDamages] = None
    licensing_benchmark: Optional[LicensingBenchmark] = None
    remediation_estimate: Optional[RemediationCostEstimate] = None
    comparable_cases: List[ComparableCase] = Field(default_factory=list)
    evidence_ids: List[str] = Field(default_factory=list)
    methodology: str = "Multi-Factor Clearance Exposure Modeling (Statutory + Market Licensing + Remediation Cost Delta)"
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def id(self) -> str:
        return self.exposure_id
