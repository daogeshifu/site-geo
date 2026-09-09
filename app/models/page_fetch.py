from pydantic import BaseModel, Field


class PageFetchMetadata(BaseModel):
    fetched_at: str | None = None
    status_code: int | None = None
    response_time_ms: int | None = None
    response_headers: dict[str, str] = Field(default_factory=dict)
    source_key: str | None = None
    source_truncated: bool = False
