"""Scouting run execution tracking model."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

from artemis.models.common import utc_now
from artemis.utils.ids import generate_id


class ScoutingRun(BaseModel):
    """Execution history record for an automated scouting run."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(
        default_factory=lambda: generate_id("run"),
        description="Unique identifier for the scouting run.",
    )
    directory_url: str = Field(
        ...,
        description="Target university faculty directory URL.",
    )
    keywords: list[str] = Field(
        default_factory=list,
        description="Target research keywords queried.",
    )
    faculty_found: int = Field(
        default=0,
        description="Number of faculty members discovered.",
    )
    papers_found: int = Field(
        default=0,
        description="Number of academic papers retrieved.",
    )
    status: str = Field(
        default="completed",
        description="Execution status: 'completed', 'failed', or 'in_progress'.",
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Error details if the scouting run failed.",
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        description="Timestamp when the run was initiated.",
    )
