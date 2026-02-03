
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import List, Optional
from pydantic import BaseModel

from api.dependencies import get_neo4j_client
from api.models.schemas import GitHubIngestRequest, IngestRequest, IngestResponse
from db import Neo4jClient
from ingestion.repo_ingestion_engine import AdvancedIngestionEngine
from ingestion.github_client import GitHubAuthError

router = APIRouter()


@router.post("/repository", response_model=IngestResponse)
async def ingest_repository(
    request: IngestRequest,
    neo4j_client: Neo4jClient = Depends(get_neo4j_client)
):
   
    try:
        # Create advanced ingestion engine
        engine = AdvancedIngestionEngine(neo4j_client)
        
        # Setup schema if needed
        engine.setup()

      
        local_path = request.repo_url  # Temporary - assume local path for testing

        # Perform advanced ingestion
        stats = engine.ingest_repository(
            repo_url=request.repo_url,
            username=request.username,
            repo_name=request.repo_name,
            clear_existing=request.clear_existing,
            local_path=local_path
        )

        # Close engine connections
        engine.close()

        if stats.errors:
            return IngestResponse(
                message=f"Ingestion completed with {len(stats.errors)} errors",
                status="completed_with_errors"
            )
        else:
            return IngestResponse(
                message="Advanced repository ingestion completed successfully",
                status="success"
            )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Advanced ingestion failed: {str(e)}"
        )


@router.post("/setup")
async def setup_database(neo4j_client: Neo4jClient = Depends(get_neo4j_client)):
   
    try:
        engine = AdvancedIngestionEngine(neo4j_client)
        engine.setup()
        engine.close()
        
        return {
            "status": "success", 
            "message": "Advanced database schema initialized successfully"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Schema setup failed: {str(e)}"
        )





@router.post("/github")
async def ingest_github_repository(
    request: GitHubIngestRequest,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    neo4j_client: Neo4jClient = Depends(get_neo4j_client)
):
   
    try:
        # Create advanced ingestion engine
        engine = AdvancedIngestionEngine(neo4j_client)
        
        # Setup schema if needed
        engine.setup()

        # Perform GitHub repository ingestion
        stats = await engine.ingest_github_repository(
            owner=request.owner,
            repo_name=request.repo_name,
            branch=request.branch,
            clear_existing=request.clear_existing
        )

        engine.close()

        return {
            "status": "success",
            "message": f"GitHub repository {request.owner}/{request.repo_name} ingested successfully",
            "repository_id": f"{request.owner}/{request.repo_name}",
            "stats": {
                "files_processed": stats.files_processed,
                "files_skipped": stats.files_skipped,
                "classes_found": stats.classes_found,
                "functions_found": stats.functions_found,
                "imports_found": stats.imports_found,
                "total_lines": stats.total_lines,
                "errors": stats.errors
            }
        }
    except GitHubAuthError as e:
        raise HTTPException(
            status_code=403,
            detail=f"GitHub authentication error: {str(e)}"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Configuration error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"GitHub repository ingestion failed: {str(e)}"
        )
