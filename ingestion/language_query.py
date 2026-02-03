import re
import logging
from .core.database import DatabaseManager
from .utils.debug_log import debug_log

logger = logging.getLogger(__name__)

class Advanced_language_query:
    """
    Tool implementation for executing language-specific Cypher queries.
    
    Simplified version for initial integration.
    """

    Supported_queries = {
        "repository": "Repository",
        "directory": "Directory", 
        "file": "File",
        "module": "Module",
        "function": "Function",
        "class": "Class",
        "struct": "Struct",
        "enum": "Enum",
        "union": "Union",
        "macro": "Macro",
        "variable": "Variable"
    }

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def advanced_language_query(self, language: str, query: str):
        """Execute a basic query for a specific language."""
        query = query.strip().lower()
        if query not in self.Supported_queries:
            raise ValueError(
                f"Unsupported query type '{query}'"
                f"Supported: {', '.join(self.Supported_queries.keys())}"
            )
        
        label = self.Supported_queries[query]
        
        # Basic Cypher query
        cypher_query = f"MATCH (n:{label}) RETURN n LIMIT 50"
        
        try:
            debug_log(f"Executing Cypher query: {cypher_query}")
            with self.db_manager.get_driver().session() as session:
                result = session.run(cypher_query)
                records = [record.data() for record in result]

                return {
                    "success": True,
                    "language": language,
                    "query": cypher_query,
                    "results": records 
                }
        except Exception as e:
            debug_log(f"Error executing Cypher query: {str(e)}")
            return {
                "error": "An unexpected error occurred while executing the query.",
                "details": str(e)
            }




