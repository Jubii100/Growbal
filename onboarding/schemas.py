from typing import Any, List, Optional
from enum import Enum
from pydantic import BaseModel, Field





class ItemStatus(str, Enum):
    """Lifecycle status of a checklist item within onboarding."""
    PENDING = "PENDING"
    ASKED = "ASKED"
    VERIFIED = "VERIFIED"
    AUTO_FILLED = "AUTO_FILLED"


class ChecklistItem(BaseModel):

    key: str = Field(
        ..., description="Slug-like unique key, lowercase, words separated by underscores"
    )
    prompt: str = Field(
        ..., description="Insightful and inquisitive question to ask the provider"
    )
    required: bool = Field(
        ..., description="True if required to proceed or complete onboarding"
    )
    status: ItemStatus = Field(
        default=ItemStatus.PENDING,
        description="Workflow status; always PENDING for initial checklist",
    )
    # NOTE: Restrict to JSON-safe primitive to satisfy OpenAI structured output schema.
    # For initial checklist generation this will be null; downstream can coerce types as needed.
    value: Optional[str] = Field(
        default=None,
        description="The collected answer; null initially and until provided/auto-filled",
    )


class ChecklistResponse(BaseModel):
    """Top-level response containing the list of checklist items."""

    checklist: List[ChecklistItem] = Field(
        ..., description="List of checklist items to collect during onboarding"
    )


class SearchQuery(BaseModel):
    """A generated search query for finding provider information."""

    text: str = Field(..., description="Search query text")
    intent: str = Field(
        default="provider_discovery",
        description="High-level intent of the query",
    )


class WebSearchResult(BaseModel):
    """Single web search result returned by the search tool."""

    title: str = Field(..., description="Result title")
    url: str = Field(..., description="Destination URL")
    snippet: Optional[str] = Field(default=None, description="Short snippet/description")
    source: Optional[str] = Field(default="openai_web_search", description="Search backend")
    score: Optional[float] = Field(default=None, description="Relevance score (0-1)")


class WebSearchResponse(BaseModel):
    """Structured response for a web search operation."""

    query: str = Field(..., description="Original query text")
    results: List[WebSearchResult] = Field(default_factory=list)


class FetchedPage(BaseModel):
    """Fetched raw page content from ScrapingFish (rendered)."""

    url: str
    status_code: int
    html: str
    fetched_at: str


class ParsedPage(BaseModel):
    """Parsed natural text extracted from a fetched page."""

    url: str
    title: Optional[str] = None
    text: str = Field(..., description="Natural text content only (headings, paragraphs)")
    headings: List[str] = Field(default_factory=list)
    paragraphs: List[str] = Field(default_factory=list)
    word_count: int = 0
    source: str = Field(default="scrapingfish")


# -------------------- Structured Output Models for LLM --------------------

class GenerateSearchQueriesResponse(BaseModel):
    """Structured output for generated search queries."""
    queries: List[SearchQuery] = Field(default_factory=list)


class RerankResponse(BaseModel):
    """Structured output for reranked results."""
    ordered_urls: List[str] = Field(default_factory=list)


class ModificationItem(BaseModel):
    key: str
    question: str
    type: str
    reason: Optional[str] = None


class ItemsToRemoveEntry(BaseModel):
    key: str
    reason: Optional[str] = None


class ExtractChecklistModificationsResponse(BaseModel):
    mandatory_additions: List[ModificationItem] = Field(default_factory=list)
    recommended_additions: List[ModificationItem] = Field(default_factory=list)
    items_to_remove: List[ItemsToRemoveEntry] = Field(default_factory=list)


class ExtractAnswerFromContentResponse(BaseModel):
    value: str
    confidence: float
    source: str
    evidence: str


class TextResponse(BaseModel):
    """Generic single-text response for clarifying questions and confirmations."""
    text: str


class ProfileSummaryResponse(BaseModel):
    """Structured output for comprehensive provider profile summary."""
    summary: str = Field(
        ..., 
        description="Comprehensive, professional summary of the service provider's profile, capabilities, and business details"
    )
