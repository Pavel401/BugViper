from dotenv import load_dotenv

# Load environment variables BEFORE any imports that use them (e.g. Firebase)
load_dotenv()

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import auth, ingestion, query, repository, webhook
from api.services.firebase_service import firebase_service  # noqa: F401 — init on import
import uvicorn


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager.

    Handles startup and shutdown events.
    """
    # Startup
    yield
    # Shutdown - cleanup will be handled by new system


# Create FastAPI application
app = FastAPI(
    title="BugViper Code Ingestion API",
    description="""
    Advanced Multi-Language Code Analysis and Ingestion API.

    ## Features

    * **Multi-Language Support** - Python, TypeScript, JavaScript, Go, Rust, Java, C++, and more
    * **Advanced Code Analysis** - Complexity metrics, dead code detection, dependency analysis
    * **Intelligent Graph Storage** - Neo4j-based code relationships and structure
    * **Agent-Based Code Review** - AI-powered code analysis and review

    ## Getting Started

    1. Set up your Neo4j database credentials in environment variables
    2. Call `/api/v1/ingest/setup` to initialize the schema
    3. Use `/api/v1/ingest/repository` to ingest a repository
    4. Query your code using the various endpoints
    """,
    version="0.2.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(
    ingestion.router,
    prefix="/api/v1/ingest",
    tags=["Ingestion"]
)

app.include_router(
    query.router,
    prefix="/api/v1/query",
    tags=["Query"]
)

app.include_router(
    repository.router,
    prefix="/api/v1/repos",
    tags=["Repository"]
)

app.include_router(
    webhook.router,
    prefix="/api/v1/webhook",
    tags=["Webhook"]
)

app.include_router(
    auth.router,
    prefix="/api/v1/auth",
    tags=["Auth"]
)






def run_server():
    """
    Run the API server.

    This function is used as an entry point for the CLI command.
    """
    uvicorn.run(
        "api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )


if __name__ == "__main__":
    run_server()
