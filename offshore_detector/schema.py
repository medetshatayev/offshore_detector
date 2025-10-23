"""
Pydantic schemas for structured LLM output and transaction data.
Ensures type safety and validation throughout the pipeline.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Literal
from datetime import datetime


class MatchSignal(BaseModel):
    """Signal from simple fuzzy matching."""
    value: Optional[str] = None
    score: Optional[float] = Field(None, ge=0.0, le=1.0)


class TransactionSignals(BaseModel):
    """All signals collected for a transaction."""
    swift_country_code: Optional[str] = None
    swift_country_name: Optional[str] = None
    is_offshore_by_swift: Optional[bool] = None
    country_name_match: MatchSignal = Field(default_factory=MatchSignal)
    country_code_match: MatchSignal = Field(default_factory=MatchSignal)
    city_match: MatchSignal = Field(default_factory=MatchSignal)


class Classification(BaseModel):
    """Classification result with label and confidence."""
    label: Literal["OFFSHORE_YES", "OFFSHORE_SUSPECT", "OFFSHORE_NO"]
    confidence: float = Field(..., ge=0.0, le=1.0)


class TransactionClassification(BaseModel):
    """
    Complete structured output from LLM for a single transaction.
    This is the exact schema the LLM must conform to.
    """
    transaction_id: Optional[str | int] = None
    direction: Literal["incoming", "outgoing"]
    amount_kzt: float
    signals: TransactionSignals
    classification: Classification
    reasoning_short_ru: str = Field(..., min_length=10, max_length=500)
    sources: List[str] = Field(default_factory=list)
    llm_error: Optional[str] = None
    
    @field_validator('sources')
    @classmethod
    def validate_sources(cls, v):
        """Ensure sources are valid URLs if present."""
        if not v:
            return []
        return [url.strip() for url in v if url and isinstance(url, str)]


class TransactionMetadata(BaseModel):
    """Metadata added during processing."""
    direction: Literal["incoming", "outgoing"]
    amount_kzt_normalized: float
    processed_at: datetime = Field(default_factory=datetime.now)
    row_index: Optional[int] = None


# Mapping for Russian labels used in output
LABEL_MAP_RU = {
    "OFFSHORE_YES": "ОФШОР: ДА",
    "OFFSHORE_SUSPECT": "ОФШОР: ПОДОЗРЕНИЕ",
    "OFFSHORE_NO": "ОФШОР: НЕТ"
}
