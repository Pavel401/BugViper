"""Pydantic models for the code review workflow."""

from typing import Any, Literal
from pydantic import BaseModel, Field


class Issue(BaseModel):
    """Code review issue/finding."""

    severity: Literal["critical", "high", "medium", "low"] = Field(
        description="Issue severity level"
    )
    category: str = Field(description="Issue category (e.g., 'security', 'bug', 'style')")
    title: str = Field(description="Short title of the issue")
    file: str = Field(description="File path where issue was found")
    line_start: int = Field(description="Starting line number")
    line_end: int | None = Field(default=None, description="Ending line number (optional)")
    description: str = Field(description="Detailed description of the issue")
    suggestion: str | None = Field(default=None, description="Suggested fix (optional)")
    impact: str | None = Field(default=None, description="Impact assessment (optional)")


class AgentFindings(BaseModel):
    """Structured output from each specialist agent."""

    issues: list[Issue] = Field(default_factory=list)
    positive_findings: list[str] = Field(default_factory=list)


class ReviewResults(BaseModel):
    """Results from code review analysis."""

    summary: str = Field(description="Brief 1-2 sentence overview of the review")
    issues: list[Issue] = Field(default_factory=list, description="List of issues found")
    positive_findings: list[str] = Field(
        default_factory=list, description="Positive aspects of the code"
    )
    error: str | None = Field(default=None, description="Error message if review failed")


class ContextData(BaseModel):
    """Impact analysis and dependency graph data."""

    files_changed: list[str] = Field(default_factory=list)
    modified_symbols: list[str] = Field(default_factory=list)
    total_callers: int = 0
    risk_level: Literal["low", "medium", "high"] = "low"


class ReviewResult(BaseModel):
    """Complete output from code review workflow."""

    should_proceed: bool = Field(description="Whether review was performed")
    intent_reason: str = Field(description="Reason for proceed/skip decision")
    context: ContextData | None = None
    review_results: ReviewResults = Field(
        default_factory=lambda: ReviewResults(summary="", issues=[], positive_findings=[]),
    )
    final_comment: str = Field(default="")
