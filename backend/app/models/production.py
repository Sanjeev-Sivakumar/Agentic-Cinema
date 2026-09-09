from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
import uuid
from pydantic import BaseModel, Field

class ProductionStatus(str, Enum):
    DRAFT = "DRAFT"
    READY_FOR_ANALYSIS = "READY_FOR_ANALYSIS"
    ANALYZING = "ANALYZING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class ProductionCreate(BaseModel):
    title: str
    description: Optional[str] = None
    director: Optional[str] = None
    studio: Optional[str] = None
    budget_tier: Optional[str] = "Independent"
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ProductionUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    script_path: Optional[str] = None
    footage_path: Optional[str] = None
    status: Optional[ProductionStatus] = None
    metadata: Optional[Dict[str, Any]] = None

class Production(BaseModel):
    id: str = Field(default_factory=lambda: f"prod_{uuid.uuid4().hex[:10]}")
    title: str
    description: Optional[str] = None
    director: Optional[str] = None
    studio: Optional[str] = None
    budget_tier: Optional[str] = "Independent"
    script_path: Optional[str] = None
    footage_path: Optional[str] = None
    status: ProductionStatus = ProductionStatus.DRAFT
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)
