from typing import Any, Dict
from dataclasses import asdict
from datetime import datetime

from common import debug_log
from common.job_models import JobStatus
from ingestion_service.core.jobs import JobManager
from ingestion_service.core.tree_sitter_router import GraphBuilder
from ...api.services.code_search import CodeFinder

def list_indexed_repositories(code_finder: CodeFinder, **args) -> Dict[str, Any]:
    """Tool to list indexed repositories."""
    try:
        debug_log("Listing indexed repositories.")
        results = code_finder.list_indexed_repositories()
        return {
            "success": True,
            "repositories": results
        }
    except Exception as e:
        debug_log(f"Error listing indexed repositories: {str(e)}")
        return {"error": f"Failed to list indexed repositories: {str(e)}"}

def delete_repository(graph_builder: GraphBuilder, **args) -> Dict[str, Any]:
    """Tool to delete a repository from the graph."""
    repo_path = args.get("repo_path")
    try:
        debug_log(f"Deleting repository: {repo_path}")
        if graph_builder.delete_repository_from_graph(repo_path):
            return {
                "success": True,
                "message": f"Repository '{repo_path}' deleted successfully."
            }
        else:
                return {
                "success": False,
                "message": f"Repository '{repo_path}' not found in the graph."
            }
    except Exception as e:
        debug_log(f"Error deleting repository: {str(e)}")
        return {"error": f"Failed to delete repository: {str(e)}"}

def check_job_status(job_manager: JobManager, **args) -> Dict[str, Any]:
    """Tool to check job status"""
    job_id = args.get("job_id")
    if not job_id:
        return {"error": "Job ID is a required argument."}
            
    try:
        job = job_manager.get_job(job_id)
        
        if not job:
            return {
                "success": True, # Return success to avoid generic error wrapper
                "status": "not_found",
                "message": f"Job with ID '{job_id}' not found. The ID may be incorrect or the job may have been cleared after a server restart."
            }
        
        job_dict = asdict(job)
        
        if job.status == JobStatus.RUNNING:
            if job.estimated_time_remaining:
                remaining = job.estimated_time_remaining
                job_dict["estimated_time_remaining_human"] = (
                    f"{int(remaining // 60)}m {int(remaining % 60)}s" 
                    if remaining >= 60 else f"{int(remaining)}s"
                )
            
            if job.start_time:
                elapsed = (datetime.now() - job.start_time).total_seconds()
                job_dict["elapsed_time_human"] = (
                    f"{int(elapsed // 60)}m {int(elapsed % 60)}s" 
                    if elapsed >= 60 else f"{int(elapsed)}s"
                )
        
        elif job.status == JobStatus.COMPLETED and job.start_time and job.end_time:
            duration = (job.end_time - job.start_time).total_seconds()
            job_dict["actual_duration_human"] = (
                f"{int(duration // 60)}m {int(duration % 60)}s" 
                if duration >= 60 else f"{int(duration)}s"
            )
        
        job_dict["start_time"] = job.start_time.strftime("%Y-%m-%d %H:%M:%S")
        if job.end_time:
            job_dict["end_time"] = job.end_time.strftime("%Y-%m-%d %H:%M:%S")
        
        job_dict["status"] = job.status.value
        
        return {"success": True, "job": job_dict}
    
    except Exception as e:
        debug_log(f"Error checking job status: {str(e)}")
        return {"error": f"Failed to check job status: {str(e)}"}





def get_repository_stats(code_finder: CodeFinder, **args) -> Dict[str, Any]:
    """Tool to get statistics about indexed repositories."""
    from pathlib import Path
    
    repo_path = args.get("repo_path")
    
    try:
        debug_log(f"Getting stats for: {repo_path or 'all repositories'}")
        
        with code_finder.db_manager.get_driver().session() as session:
            if repo_path:
                # Stats for specific repository
                repo_path_obj = str(Path(repo_path).resolve())
                
                # Check if repository exists
                repo_query = """
                MATCH (r:Repository {path: $path})
                RETURN r
                """
                result = session.run(repo_query, path=repo_path_obj)
                if not result.single():
                    return {
                        "success": False,
                        "error": f"Repository not found: {repo_path_obj}"
                    }
                
                # Get stats for specific repo
                stats_query = """
                MATCH (r:Repository {path: $path})-[:CONTAINS]->(f:File)
                WITH r, count(f) as file_count, f
                OPTIONAL MATCH (f)-[:CONTAINS]->(func:Function)
                OPTIONAL MATCH (f)-[:CONTAINS]->(cls:Class)
                OPTIONAL MATCH (f)-[:IMPORTS]->(m:Module)
                RETURN 
                    file_count,
                    count(DISTINCT func) as function_count,
                    count(DISTINCT cls) as class_count,
                    count(DISTINCT m) as module_count
                """
                result = session.run(stats_query, path=repo_path_obj)
                record = result.single()
                
                return {
                    "success": True,
                    "repository": repo_path_obj,
                    "stats": {
                        "files": record["file_count"] if record else 0,
                        "functions": record["function_count"] if record else 0,
                        "classes": record["class_count"] if record else 0,
                        "modules": record["module_count"] if record else 0
                    }
                }
            else:
                # Overall database stats
                stats_query = """
                MATCH (r:Repository)
                OPTIONAL MATCH (f:File)
                OPTIONAL MATCH (func:Function)
                OPTIONAL MATCH (cls:Class)
                OPTIONAL MATCH (m:Module)
                RETURN 
                    count(DISTINCT r) as repo_count,
                    count(DISTINCT f) as file_count,
                    count(DISTINCT func) as function_count,
                    count(DISTINCT cls) as class_count,
                    count(DISTINCT m) as module_count
                """
                result = session.run(stats_query)
                record = result.single()
                
                if record and record["repo_count"] > 0:
                    return {
                        "success": True,
                        "stats": {
                            "repositories": record["repo_count"],
                            "files": record["file_count"],
                            "functions": record["function_count"],
                            "classes": record["class_count"],
                            "modules": record["module_count"]
                        }
                    }
                else:
                    return {
                        "success": True,
                        "stats": {},
                        "message": "No data indexed yet"
                    }
    
    except Exception as e:
        debug_log(f"Error getting stats: {str(e)}")
        return {"error": f"Failed to get stats: {str(e)}"}
