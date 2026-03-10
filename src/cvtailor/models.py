from __future__ import annotations

from pydantic import BaseModel, Field


class TailorRequest(BaseModel):
    cv_text: str
    job_description: str
    target_region: str = "uk"


class TailorResult(BaseModel):
    fit_summary: str
    missing_keywords: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    revised_summary: str