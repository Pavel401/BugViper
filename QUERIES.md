# Useful Neo4j Queries for GraphRAG

This file contains useful Cypher queries to explore your interconnected code graph.

## Basic Statistics

### Count all nodes by type
```cypher
MATCH (n)
RETURN labels(n)[0] as NodeType, count(n) as Count
ORDER BY Count DESC
```

### Count all relationships by type
```cypher
MATCH ()-[r]->()
RETURN type(r) as RelationshipType, count(r) as Count
ORDER BY Count DESC
```

## Cross-File Relationships

### Find all cross-file function calls
```cypher
MATCH (f1:File)-[:CONTAINS]->(fn1:Function)
MATCH (fn1)-[:CALLS]->(fn2:Function)
MATCH (f2:File)-[:CONTAINS]->(fn2)
WHERE f1.path <> f2.path
RETURN f1.path as CallerFile,
       fn1.name as CallerFunction,
       f2.path as CalleeFile,
       fn2.name as CalleeFunction
LIMIT 50
```

### Visualize cross-file dependencies (use in Neo4j Browser)
```cypher
MATCH (f1:File)-[:CONTAINS]->(fn1:Function)-[:CALLS]->(fn2:Function)<-[:CONTAINS]-(f2:File)
WHERE f1.path <> f2.path
RETURN f1, fn1, fn2, f2
LIMIT 100
```

### Find files with the most imports
```cypher
MATCH (f:File)-[:IMPORTS]->(m:Module)
RETURN f.path,
       f.language,
       count(m) as ImportCount
ORDER BY ImportCount DESC
LIMIT 20
```

### Find import chains (transitive dependencies)
```cypher
MATCH path = (f1:File)-[:IMPORTS*1..3]->(m:Module)
RETURN f1.path,
       length(path) as Depth,
       collect(m.name) as ImportChain
ORDER BY Depth DESC
LIMIT 20
```

## Function Analysis

### Most called functions (highest incoming degree)
```cypher
MATCH (caller:Function)-[:CALLS]->(callee:Function)
RETURN callee.name,
       callee.id,
       count(caller) as CalledByCount
ORDER BY CalledByCount DESC
LIMIT 20
```

### Functions that call many others (highest outgoing degree)
```cypher
MATCH (caller:Function)-[:CALLS]->(callee:Function)
RETURN caller.name,
       caller.id,
       count(callee) as CallsCount
ORDER BY CallsCount DESC
LIMIT 20
```

### Find unused functions (defined but never called)
```cypher
MATCH (fn:Function)
WHERE NOT (()-[:CALLS]->(fn))
RETURN fn.name, fn.id
LIMIT 50
```

### Find leaf functions (don't call anything else)
```cypher
MATCH (fn:Function)
WHERE NOT (fn)-[:CALLS]->()
RETURN fn.name, fn.id
LIMIT 50
```

### Analyze a specific function's dependencies
```cypher
MATCH (fn:Function {name: "your_function_name"})
OPTIONAL MATCH (fn)-[:CALLS]->(called:Function)
OPTIONAL MATCH (f:File)-[:CONTAINS]->(fn)
OPTIONAL MATCH (f)-[:IMPORTS]->(m:Module)
RETURN fn,
       collect(DISTINCT called) as DirectCalls,
       collect(DISTINCT m) as FileImports
```

## File Dependency Analysis

### Files with most outgoing dependencies
```cypher
MATCH (f:File)-[:CONTAINS]->(fn:Function)-[:CALLS]->(target:Function)<-[:CONTAINS]-(targetFile:File)
WHERE f.path <> targetFile.path
RETURN f.path,
       count(DISTINCT targetFile) as DependsOnFileCount,
       collect(DISTINCT targetFile.path) as DependentFiles
ORDER BY DependsOnFileCount DESC
LIMIT 20
```

### Files with most incoming dependencies (most depended upon)
```cypher
MATCH (f:File)-[:CONTAINS]->(fn:Function)<-[:CALLS]-(caller:Function)<-[:CONTAINS]-(callerFile:File)
WHERE f.path <> callerFile.path
RETURN f.path,
       count(DISTINCT callerFile) as UsedByFileCount,
       collect(DISTINCT callerFile.path) as UsingFiles
ORDER BY UsedByFileCount DESC
LIMIT 20
```

### Find circular dependencies between files
```cypher
MATCH path = (f1:File)-[:CONTAINS]->(:Function)-[:CALLS]->(:Function)<-[:CONTAINS]-(f2:File)
            -[:CONTAINS]->(:Function)-[:CALLS]->(:Function)<-[:CONTAINS]-(f1)
WHERE f1.path < f2.path
RETURN f1.path, f2.path
LIMIT 50
```

### Visualize a file's dependency network
```cypher
MATCH (f:File {path: "your/file/path.py"})
MATCH (f)-[:CONTAINS]->(fn:Function)
OPTIONAL MATCH (fn)-[:CALLS]->(target:Function)
OPTIONAL MATCH (f)-[:IMPORTS]->(m:Module)
RETURN f, fn, target, m
```

## Code Structure Insights

### Find utility/helper files (many incoming, few outgoing)
```cypher
MATCH (f:File)-[:CONTAINS]->(fn:Function)
WITH f, fn
OPTIONAL MATCH (fn)<-[:CALLS]-(caller:Function)
OPTIONAL MATCH (fn)-[:CALLS]->(callee:Function)
WITH f,
     count(DISTINCT caller) as IncomingCalls,
     count(DISTINCT callee) as OutgoingCalls
WHERE IncomingCalls > 5 AND OutgoingCalls < 3
RETURN f.path, IncomingCalls, OutgoingCalls
ORDER BY IncomingCalls DESC
```

### Find God objects/files (too many dependencies)
```cypher
MATCH (f:File)
OPTIONAL MATCH (f)-[:IMPORTS]->(m:Module)
OPTIONAL MATCH (f)-[:CONTAINS]->(fn:Function)-[:CALLS]->(target:Function)
WITH f,
     count(DISTINCT m) as ImportCount,
     count(DISTINCT target) as CallCount
WHERE ImportCount + CallCount > 50
RETURN f.path, ImportCount, CallCount, ImportCount + CallCount as TotalDeps
ORDER BY TotalDeps DESC
```

### Find isolated components (no cross-file relationships)
```cypher
MATCH (f:File)
WHERE NOT (f)-[:IMPORTS]->()
  AND NOT (f)-[:CONTAINS]->()-[:CALLS]->()<-[:CONTAINS]-(:File)
RETURN f.path, f.language
```

## Class Analysis

### Find classes and their usage
```cypher
MATCH (c:Class)
OPTIONAL MATCH (c)<-[:USES]-(user)
RETURN c.name,
       c.id,
       count(user) as UsageCount
ORDER BY UsageCount DESC
```

### Class hierarchy (if INHERITS relationships are added)
```cypher
MATCH path = (child:Class)-[:INHERITS*]->(parent:Class)
RETURN child.name,
       length(path) as InheritanceDepth,
       parent.name
ORDER BY InheritanceDepth DESC
```

## Code Quality Metrics

### Complexity: Files by number of functions
```cypher
MATCH (f:File)-[:CONTAINS]->(fn:Function)
RETURN f.path,
       count(fn) as FunctionCount
ORDER BY FunctionCount DESC
LIMIT 20
```

### Coupling: Function call fan-in and fan-out
```cypher
MATCH (fn:Function)
OPTIONAL MATCH (fn)<-[:CALLS]-(caller:Function)
OPTIONAL MATCH (fn)-[:CALLS]->(callee:Function)
WITH fn,
     count(DISTINCT caller) as FanIn,
     count(DISTINCT callee) as FanOut
RETURN fn.name,
       fn.id,
       FanIn,
       FanOut,
       FanIn + FanOut as TotalCoupling
ORDER BY TotalCoupling DESC
LIMIT 20
```

### Find duplicate or similar function names
```cypher
MATCH (fn:Function)
WITH fn.name as FunctionName, collect(fn) as Functions
WHERE size(Functions) > 1
RETURN FunctionName,
       size(Functions) as Count,
       [f in Functions | f.id] as Locations
ORDER BY Count DESC
```

## Path Finding

### Find shortest path between two functions
```cypher
MATCH (start:Function {name: "function1"})
MATCH (end:Function {name: "function2"})
MATCH path = shortestPath((start)-[:CALLS*]-(end))
RETURN path
```

### Find all paths between files (via function calls)
```cypher
MATCH (f1:File {path: "file1.py"})-[:CONTAINS]->(fn1:Function)
MATCH (f2:File {path: "file2.py"})-[:CONTAINS]->(fn2:Function)
MATCH path = (fn1)-[:CALLS*1..5]->(fn2)
RETURN path
LIMIT 10
```

### Impact analysis: What's affected if I change this function?
```cypher
MATCH (fn:Function {name: "target_function"})
MATCH path = (fn)<-[:CALLS*1..3]-(dependent:Function)
RETURN path
```

## Development Insights

### Recently modified files with most dependencies (if you add timestamps)
```cypher
MATCH (f:File)
WHERE f.modified_date > datetime() - duration('P30D')
OPTIONAL MATCH (f)-[:IMPORTS]->(m:Module)
OPTIONAL MATCH (f)-[:CONTAINS]->()-[:CALLS]->()
RETURN f.path,
       f.modified_date,
       count(DISTINCT m) as ImportCount
ORDER BY ImportCount DESC
```

### Find entry points (functions called externally, not by other functions)
```cypher
MATCH (fn:Function)
WHERE NOT ()<-[:CALLS]-(fn)
  AND NOT fn.name STARTS WITH "_"  // Exclude private functions
RETURN fn.name, fn.id
LIMIT 50
```

## Export Data

### Export dependency matrix as CSV
```cypher
MATCH (f1:File)-[:CONTAINS]->(fn1:Function)-[:CALLS]->(fn2:Function)<-[:CONTAINS]-(f2:File)
RETURN f1.path as Source, f2.path as Target, count(*) as CallCount
ORDER BY Source, Target
```

### Export for visualization tools (D3, Gephi, etc.)
```cypher
// Nodes
MATCH (f:File)
RETURN id(f) as id, f.path as label, "File" as type

// Edges
MATCH (f1:File)-[:CONTAINS]->(:Function)-[:CALLS]->(:Function)<-[:CONTAINS]-(f2:File)
WHERE f1.path <> f2.path
RETURN id(f1) as source, id(f2) as target, "DEPENDS_ON" as type
```

## Tips for Using These Queries

1. **Neo4j Browser**: Copy queries into Neo4j Browser at http://localhost:7474
2. **Limit results**: Always use LIMIT for large graphs to avoid browser overload
3. **Visualization**: Queries returning nodes and relationships render as interactive graphs
4. **Export**: Use CSV export option in Neo4j Browser for further analysis
5. **Customize**: Replace placeholder values (e.g., "your_function_name") with your actual data
6. **Performance**: Add indexes on frequently queried properties
