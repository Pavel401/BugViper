from typing import Optional
from fastapi import Depends
import os
from db import Neo4jClient

def get_neo4j_client() -> Neo4jClient:
    """Get Neo4j database client from environment variables."""
    
    # Get environment variables
    neo4j_uri = os.getenv("NEO4J_URI", "")
    neo4j_username = os.getenv("NEO4J_USERNAME", "")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "")
    neo4j_database = os.getenv("NEO4J_DATABASE", "")

    print("Connecting to Neo4j with the following parameters:")
    print(f"URI: {neo4j_uri}")
    print(f"User: {neo4j_username}")
    print(f"Database: {neo4j_database}")
    print("Password: {}  # Do not print password for security reasons".format("********"))
    
    # Check if required environment variables are set
    if not neo4j_uri:
        raise ValueError("NEO4J_URI environment variable is required")
    if not neo4j_username:
        raise ValueError("NEO4J_USERNAME environment variable is required")
    if not neo4j_password:
        raise ValueError("NEO4J_PASSWORD environment variable is required")
    
    return Neo4jClient(
        uri=neo4j_uri,
        user=neo4j_username,
        password=neo4j_password,
        database=neo4j_database
    )
