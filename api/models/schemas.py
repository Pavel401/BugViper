from typing import Optional, List
from pydantic import BaseModel, Field

from typing import Optional
from pydantic import BaseModel


class GitHubIngestRequest(BaseModel):
    owner: str
    repo_name: str
    branch: Optional[str] = None
    clear_existing: bool = False

class IngestRequest(BaseModel):
    """Request schema for repository ingestion."""
    repo_url: str = Field(..., description="Git repository URL")
    username: Optional[str] = Field(None, description="Owner/user name")
    repo_name: Optional[str] = Field(None, description="Repository name") 
    clear_existing: bool = Field(False, description="Clear existing data")
    languages: Optional[List[str]] = Field(None, description="Languages to process")


class IngestResponse(BaseModel):
    """Response schema for repository ingestion."""
    message: str
    status: str



class QueryResponse(BaseModel):
    """Basic response schema for queries."""
    message: str
    data: Optional[dict] = None
