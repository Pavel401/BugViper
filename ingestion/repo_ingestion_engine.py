
import os
import asyncio
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from db import Neo4jClient, CodeGraphSchema, GraphIngestionService
from .core.jobs import JobManager, JobStatus
from .graph_builder import GraphBuilder
from .github_client import GitHubClient, GitHubAuthError
from .github_client import GitHubClient, GitHubAuthError


@dataclass
class IngestionStats:
    """Statistics for ingestion operations."""
    files_processed: int = 0
    files_skipped: int = 0
    classes_found: int = 0
    functions_found: int = 0
    imports_found: int = 0
    total_lines: int = 0
    errors: List[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class AdvancedIngestionEngine:
    """
    Advanced ingestion engine that combines the multi-language
    capabilities with Neo4j storage and GitHub App authentication.
    """

    def __init__(self, neo4j_client: Neo4jClient):
        self.neo4j_client = neo4j_client
        self.job_manager = JobManager()
        self.graph_builder = GraphBuilder(
            self.neo4j_client, 
            self.job_manager,
            asyncio.get_event_loop()
        )
        self.schema = CodeGraphSchema(neo4j_client)
        self.ingestion_service = GraphIngestionService(neo4j_client)
        
        # Initialize GitHub client if credentials are available
        try:
            self.github_client = GitHubClient()
        except ValueError as e:
            print(f"Warning: GitHub App credentials not configured: {e}")
            self.github_client = None

    def setup(self):
        """Initialize database schema."""
        print("Setting up database schema...")
        self.schema.create_constraints_and_indexes()
        # Also setup the advanced graph schema
        self.graph_builder.create_schema()
        print("✓ Schema ready")

    def ingest_repository(
        self,
        repo_url: str,
        username: Optional[str] = None,
        repo_name: Optional[str] = None,
        clear_existing: bool = False,
        local_path: Optional[str] = None
    ) -> IngestionStats:
        """
        Ingest a repository using the advanced multi-language system.
        """
        print(f"\n{'='*60}")
        print(f"ADVANCED REPOSITORY INGESTION")
        print(f"{'='*60}")

        # Extract username and repo_name from URL if not provided
        if not username or not repo_name:
            # Basic URL parsing
            if "github.com" in repo_url:
                parts = repo_url.rstrip('/').split('/')
                if len(parts) >= 2:
                    username = username or parts[-2]
                    repo_name = repo_name or parts[-1].replace('.git', '')

        repo_id = f"{username}/{repo_name}"
        print(f"Repository: {repo_id}")
        print(f"URL: {repo_url}")

        if clear_existing:
            print(f"\n⚠️  Clearing existing data for {repo_id}...")
            self.schema.clear_repository(repo_id)
            print("✓ Existing data cleared")

        job_id = self.job_manager.create_job(
            "repository_ingestion",
            repo_url=repo_url,
            username=username,
            repo_name=repo_name,
            local_path=local_path
        )

        try:
            self.job_manager.update_job_status(job_id, JobStatus.RUNNING)

            if local_path and os.path.exists(local_path):
                analysis_path = Path(local_path)
            else:
                if not local_path:
                    raise ValueError("local_path must be provided for ingestion")
                analysis_path = Path(local_path)

            # Create user and repository nodes using existing service
            self.ingestion_service.create_user(username)
            created_repo_id = self.ingestion_service.create_repository(
                username=username,
                repo_name=repo_name,
                url=repo_url,
                local_path=str(analysis_path),
                default_branch="main"  # Default for now
            )

            print(f"Repository ID: {created_repo_id}")

            # Use the advanced graph builder to analyze the repository
            print("\nRunning advanced multi-language analysis...")
            
            # Build the graph using the advanced system
            result = asyncio.run(
                self.graph_builder.build_project_graph(
                    str(analysis_path),
                    include_dependencies=False  # Start simple
                )
            )

            # Update job status
            self.job_manager.update_job_status(job_id, JobStatus.COMPLETED)

            # Create basic stats (the advanced system would provide more detailed stats)
            stats = IngestionStats(
                files_processed=result.get('files_processed', 0),
                files_skipped=result.get('files_skipped', 0),
                classes_found=result.get('classes_found', 0),
                functions_found=result.get('functions_found', 0),
                imports_found=result.get('imports_found', 0),
                total_lines=result.get('total_lines', 0),
                errors=result.get('errors', [])
            )

            print(f"\n✅ Advanced ingestion completed!")
            print(f"Files processed: {stats.files_processed}")
            print(f"Classes found: {stats.classes_found}")
            print(f"Functions found: {stats.functions_found}")

            return stats

        except Exception as e:
            self.job_manager.update_job_status(job_id, JobStatus.FAILED)
            print(f"\n❌ Ingestion failed: {str(e)}")
            return IngestionStats(errors=[str(e)])

    def get_stats(self) -> Dict[str, Any]:
        """Get ingestion statistics."""
        return {"jobs": list(self.job_manager.jobs.values())}

    async def ingest_github_repository(
        self,
        owner: str,
        repo_name: str,
        branch: Optional[str] = None,
        clear_existing: bool = False
    ) -> IngestionStats:
        """
        Ingest a GitHub repository (public or private) using GitHub App authentication.
        
        Args:
            owner: GitHub repository owner/organization
            repo_name: Repository name
            branch: Branch to clone (optional, defaults to default branch)
            clear_existing: Whether to clear existing data before ingestion
            
        Returns:
            IngestionStats with ingestion results
        """
        if not self.github_client:
            raise ValueError("GitHub App credentials not configured. Cannot access private repositories.")
            
        repo_id = f"{owner}/{repo_name}"
        print(f"\n{'='*60}")
        print(f"GITHUB REPOSITORY INGESTION")
        print(f"{'='*60}")
        print(f"Repository: {repo_id}")

        # Check if we have access to the repository
        print("Checking repository access...")
        has_access = await self.github_client.check_repository_access(owner, repo_name)
        if not has_access:
            raise GitHubAuthError(f"No access to {repo_id}. Ensure GitHub App is installed.")

        # Get repository info
        repo_info = await self.github_client.get_repository_info(owner, repo_name)
        print(f"Access confirmed - Repository: {repo_info['full_name']} ({'private' if repo_info['private'] else 'public'})")

        # Clear existing data if requested
        if clear_existing:
            print(f"\n⚠️  Clearing existing data for {repo_id}...")
            self.schema.clear_repository(repo_id)
            print("✓ Existing data cleared")

        # Clone the repository
        print("\nCloning repository...")
        try:
            clone_path = await self.github_client.clone_repository(
                owner, 
                repo_name, 
                branch=branch
            )
            print(f"✓ Repository cloned to: {clone_path}")

            # Create job for tracking
            job_id = self.job_manager.create_job(
                "github_repository_ingestion",
                owner=owner,
                repo_name=repo_name,
                repo_url=f"https://github.com/{owner}/{repo_name}",
                clone_path=str(clone_path)
            )
            
            try:
                self.job_manager.update_job_status(job_id, JobStatus.RUNNING)

                # Create user and repository nodes using existing service
                self.ingestion_service.create_user(owner)
                created_repo_id = self.ingestion_service.create_repository(
                    username=owner,
                    repo_name=repo_name,
                    url=f"https://github.com/{owner}/{repo_name}",
                    local_path=str(clone_path),
                    default_branch=repo_info.get('default_branch', 'main')
                )

                print(f"Repository ID: {created_repo_id}")

                # Use the advanced graph builder to analyze the repository
                print("\nRunning advanced multi-language analysis...")
                
                # Build the graph using the advanced system
                result = await self.graph_builder.build_project_graph(
                    str(clone_path),
                    include_dependencies=False
                )

                # Clean up cloned repository
                print("\nCleaning up cloned repository...")
                if clone_path.exists():
                    shutil.rmtree(clone_path)
                    print("✓ Cleanup completed")

                # Update job status
                self.job_manager.update_job_status(job_id, JobStatus.COMPLETED)

                # Create stats
                stats = IngestionStats(
                    files_processed=result.get('files_processed', 0),
                    files_skipped=result.get('files_skipped', 0),
                    classes_found=result.get('classes_found', 0),
                    functions_found=result.get('functions_found', 0),
                    imports_found=result.get('imports_found', 0),
                    total_lines=result.get('total_lines', 0),
                    errors=result.get('errors', [])
                )

                print(f"\n✅ GitHub repository ingestion completed!")
                print(f"Files processed: {stats.files_processed}")
                print(f"Classes found: {stats.classes_found}")
                print(f"Functions found: {stats.functions_found}")

                return stats

            except Exception as e:
                # Clean up on error
                if clone_path.exists():
                    shutil.rmtree(clone_path)
                self.job_manager.update_job_status(job_id, JobStatus.FAILED)
                raise

        except GitHubAuthError:
            raise
        except Exception as e:
            print(f"\n❌ GitHub ingestion failed: {str(e)}")
            return IngestionStats(errors=[str(e)])

    def close(self):
        """Close database connections."""
        self.neo4j_client.close()