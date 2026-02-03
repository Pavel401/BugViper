"""
Core database utilities for the ingestion system
"""
from db import Neo4jClient

# Use Neo4jClient directly instead of wrapper
# This module can contain database utilities if needed in the future