"""
Add this as a temporary API endpoint to diagnose the graph
"""
from fastapi import APIRouter, Depends
from db.client import Neo4jClient
from api.dependencies import get_neo4j_client

router = APIRouter()

@router.get("/graph-schema")
async def diagnose_graph_schema(neo4j: Neo4jClient = Depends(get_neo4j_client)):
    """Diagnose Neo4j graph schema issues"""
    
    results = {}
    
    # 1. Check relationship types
    with neo4j.driver.session() as session:
        result = session.run("CALL db.relationshipTypes()")
        results["relationship_types"] = sorted([r["relationshipType"] for r in result])
    
    # 2. Count CALLS relationships
    with neo4j.driver.session() as session:
        result = session.run("MATCH ()-[r:CALLS]->() RETURN count(r) as count")
        results["calls_count"] = result.single()["count"]
    
    # 3. Count IMPORTS relationships
    with neo4j.driver.session() as session:
        result = session.run("MATCH ()-[r:IMPORTS]->() RETURN count(r) as count")
        results["imports_count"] = result.single()["count"]
        
        # Check properties
        if results["imports_count"] > 0:
            result = session.run("MATCH ()-[r:IMPORTS]->() RETURN keys(r) as props LIMIT 1")
            results["import_properties"] = result.single()["props"]
    
    # 4. Count INHERITS relationships
    with neo4j.driver.session() as session:
        result = session.run("MATCH ()-[r:INHERITS]->() RETURN count(r) as count")
        results["inherits_count"] = result.single()["count"]
    
    # 5. Node counts
    node_counts = {}
    with neo4j.driver.session() as session:
        for label in ["Function", "Class", "File", "Module", "Repository"]:
            result = session.run(f"MATCH (n:{label}) RETURN count(n) as count")
            node_counts[label] = result.single()["count"]
    results["node_counts"] = node_counts
    
    # 6. Check specific function
    with neo4j.driver.session() as session:
        result = session.run("""
            MATCH (f:Function {name: 'execute_pr_review'})
            RETURN f.path, f.repo
            LIMIT 1
        """)
        record = result.single()
        if record:
            results["sample_function"] = {
                "name": "execute_pr_review",
                "path": record["f.path"],
                "repo": record["f.repo"]
            }
            
            # Check CALLS relationships
            result = session.run("""
                MATCH (caller)-[:CALLS]->(f:Function {name: 'execute_pr_review'})
                RETURN count(caller) as count
            """)
            results["sample_function"]["callers"] = result.single()["count"]
            
            result = session.run("""
                MATCH (f:Function {name: 'execute_pr_review'})-[:CALLS]->(callee)
                RETURN count(callee) as count
            """)
            results["sample_function"]["callees"] = result.single()["count"]
    
    return results
