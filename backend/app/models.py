
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Request model for querying SiliconPulse intelligence"""
    query: str = Field(..., description="The query string to search for")
    k: int = Field(default=5, description="Number of top results to return")


class EvidenceItem(BaseModel):
    """Evidence item from the data stream"""
    timestamp: str | None = Field(None, description="Timestamp of the event")
    source: str | None = Field(None, description="Source of the information")
    title: str = Field(..., description="Title of the evidence")
    snippet: str = Field(..., description="Content snippet or description")
    company: str | None = Field(None, description="Related company name")
    event_type: str | None = Field(None, description="Type of event")
    url: str | None = Field(None, description="URL of the event")
    event_id: str | None = Field(None, description="Unique event ID")

class ConfidenceInfo(BaseModel):
    """Confidence information for the query results"""
    score: int = Field(..., description="Numeric confidence score (0-100)")
    label: str = Field(..., description="Confidence label (LOW/MEDIUM/HIGH)")
    reason: str = Field(..., description="Reasoning for the confidence level")


class QueryResponse(BaseModel):
    """Response model for SiliconPulse query results"""
    query: str = Field(..., description="The original query")
    evidence: list[EvidenceItem] = Field(..., description="List of evidence items")
    signal_strength: int = Field(..., description="Strength of the signal (0-100)")
    last_updated: str = Field(..., description="Timestamp of last update")
    report: str | None = Field(None, description="Generated intelligence report")
    llm_status: str | None = Field("pending", description="Status of LLM generation")
    confidence: ConfidenceInfo | None = Field(None, description="Dynamic confidence assessment")
    stream_path_used: str | None = Field(None, description="Path of the stream file used")


class InjectRequest(BaseModel):
    """Request model for manually injecting data into the stream"""
    title: str = Field(..., description="Title of the injected item")
    content: str = Field(..., description="Content of the injected item")
    timestamp: str | None = Field(None, description="Timestamp of the event")
    source: str = Field(default="ManualInject", description="Source identifier")


class InjectResponse(BaseModel):
    """Response model for data injection"""
    status: str = Field(..., description="Status of the injection operation")
    injected_at: str = Field(..., description="Timestamp when the data was injected")
    stream_path_used: str | None = Field(None, description="Path of the stream file used")


class SignalCompact(BaseModel):
    """Compact signal representation for list view"""
    timestamp: str | None = Field(None, description="Timestamp of the event")
    company: str | None = Field(None, description="Related company name")
    event_type: str | None = Field(None, description="Type of event")
    title: str = Field(..., description="Title of the evidence")
    source: str | None = Field(None, description="Source of the information")


class RadarStatus(BaseModel):
    """Radar status for a company"""
    company: str = Field(..., description="Company name")
    activity_level: str = Field(..., description="Activity level (High/Moderate/Low)")
    count: int = Field(..., description="Number of events in recent history")


class GenerateRequest(BaseModel):
    """Request model for generating insights with Gemini"""
    query: str = Field(..., description="The user query")
    context: str = Field(..., description="The formatted context string")


class GenerateResponse(BaseModel):
    """Response model for generated insights"""
    insight: str = Field(..., description="The generated insight from Gemini")


class ExportRequest(BaseModel):
    """Request model for exporting analysis"""
    query: str = Field(..., description="The original query")
    report: str = Field(..., description="The generated report content")
    evidence: list[EvidenceItem] = Field(..., description="List of evidence items")
    format: str = Field(..., description="Export format: md, json, txt, pdf")
    include_evidence: bool = Field(default=True, description="Whether to include evidence in the export")


class SourceVerifyItem(BaseModel):
    """Verification item for a source"""
    timestamp: str | None = Field(None, description="Timestamp of the event")
    source: str = Field(..., description="Source name")
    title: str = Field(..., description="Title/Headline")
    url: str | None = Field(None, description="URL if available")
    trust_level: str = Field(..., description="High, Medium, or Low")
    reason: str = Field(..., description="Reason for trust level")


class SourceVerifyResponse(BaseModel):
    """Response model for source verification"""
    query: str = Field(..., description="The query being verified")
    sources: list[SourceVerifyItem] = Field(..., description="List of verified sources")
