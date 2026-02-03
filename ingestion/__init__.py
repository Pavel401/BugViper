"""
Advanced Multi-Language Code Ingestion System

This package provides sophisticated code analysis and ingestion capabilities
for multiple programming languages using Tree-sitter parsing and Neo4j storage.
"""

from .repo_ingestion_engine import AdvancedIngestionEngine
from .github_client import GitHubClient

__all__ = ["AdvancedIngestionEngine", "GitHubClient"]