# Code Review Tool with GraphRAG

A powerful code review and analysis tool that combines Abstract Syntax Tree (AST) parsing, graph databases, and semantic search using RAG (Retrieval-Augmented Generation).

## Features

- **🤖 Conversational Chat**: Ask questions about your codebase in natural language
- **🔗 Cross-File Relationships**: Full dependency tracking with interconnected code graph
- **AST Parsing**: Uses Tree-sitter to parse code from multiple languages (Python, JavaScript, TypeScript, Java, Go)
- **Graph Database**: Stores code structure and relationships in Neo4j with IMPORTS, CALLS, and USES relationships
- **Semantic Search**: Leverages Milvus vector database for embedding-based code search
- **RAG System**: Retrieval-Augmented Generation for intelligent code review and analysis
- **Multi-language Support**: Handles Python, JavaScript, TypeScript, Java, and Go

## Architecture

```
┌─────────────────┐
│  Code Repository │
└────────┬─────────┘
         │
         ▼
┌─────────────────┐      ┌──────────────────┐
│  Tree-sitter    │      │   Code Chunks    │
│  AST Parser     │─────▶│   Extraction     │
└─────────────────┘      └────────┬─────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │                           │
                    ▼                           ▼
         ┌──────────────────┐        ┌──────────────────┐
         │     Neo4j        │        │     Milvus       │
         │  Graph Database  │        │  Vector Database │
         │  (Relationships) │        │   (Embeddings)   │
         └──────────────────┘        └──────────────────┘
                    │                           │
                    └─────────────┬─────────────┘
                                  │
                                  ▼
                         ┌─────────────────┐
                         │   RAG System    │
                         │  Code Review    │
                         └─────────────────┘
```

## Quick Start

```bash
# 1. Start databases (Docker)
docker run -d -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/password neo4j:latest
# For Milvus, see Prerequisites section

# 2. Install and configure
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your database credentials

# 3. Ingest your codebase
python main.py ingest /path/to/your/repo --clear

# 4. Start chatting with your code! 🚀
python main.py chat

💬 You: How does authentication work?
💬 You: What files depend on auth.py?
💬 You: function login
💬 You: Show me all database queries
```

## Prerequisites

1. **Python 3.8+**
2. **Neo4j Database**
   - Download: https://neo4j.com/download/
   - Or use Docker: `docker run -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/password neo4j:latest`

3. **Milvus Vector Database**
   - Install via Docker Compose: https://milvus.io/docs/install_standalone-docker.md
   - Quick start:
     ```bash
     wget https://github.com/milvus-io/milvus/releases/download/v2.3.4/milvus-standalone-docker-compose.yml -O docker-compose.yml
     docker-compose up -d
     ```

## Installation

1. Clone the repository:
   ```bash
   git clone <your-repo-url>
   cd graphrag
   ```

2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up environment variables:
   ```bash
   cp .env.example .env
   ```

4. Edit `.env` with your credentials:
   ```env
   # Neo4j Graph Database
   NEO4J_URI=bolt://localhost:7687
   NEO4J_USER=neo4j
   NEO4J_PASSWORD=your_password

   # Milvus Vector Database
   MILVUS_HOST=localhost
   MILVUS_PORT=19530

   # Embedding Model for Semantic Search
   EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

   # Optional: OpenAI API for AI-Enhanced Chat Mode
   OPENAI_API_KEY=your_openai_api_key_here  # Only needed for `chat --llm`
   ```

## Usage

### 1. Ingest a Repository

Ingest a code repository into the graph and vector databases:

```bash
python main.py ingest /path/to/your/repository
```

With clear existing data:
```bash
python main.py ingest /path/to/your/repository --clear
```

### 2. Search for Code

Semantic search across your codebase:

```bash
python main.py search "authentication function"
```

With language filter:
```bash
python main.py search "parse JSON" --language python
```

Get more results:
```bash
python main.py search "database connection" -k 10
```

### 3. Review Code Snippet

Get similar patterns and suggestions for a code snippet:

```bash
python main.py review "def login(username, password):" --language python
```

### 4. Analyze Function Usage

Find where and how a function is used:

```bash
python main.py function login
```

### 5. Chat with Your Codebase (Recommended! 🚀)

Have conversational interactions with your codebase:

```bash
python main.py chat
```

#### Basic Chat Mode (No API Key Required)

```bash
$ python main.py chat

💬 You: How does authentication work in this codebase?

🔍 Searching codebase...

🤖 Assistant:
I found 5 relevant code sections related to your query:

1. **authenticate_user** (function) in `src/auth/handler.py`
   Location: Line 45-78
   Similarity: 87.43%
   Preview: def authenticate_user(username, password): ...
   Related: 3 connected components

2. **login** (function) in `src/api/routes.py`
   Location: Line 120-145
   Similarity: 78.21%
   ...

Show source files? (y/n):
```

#### AI-Enhanced Chat Mode (Optional)

For natural language responses powered by GPT:

```bash
# Add to .env: OPENAI_API_KEY=your_key_here
python main.py chat --llm
```

#### Chat Commands

**Ask Natural Questions:**
```
💬 You: How does user authentication work?
💬 You: Where is error handling implemented?
💬 You: Show me database query functions
💬 You: What happens when a user logs in?
💬 You: Find all API endpoints
```

**Analyze Specific Function:**
```
💬 You: function authenticate_user

🤖 Assistant:
**Function: authenticate_user**
Location: `src/auth/handler.py:authenticate_user:45`
Lines: 45 - 78

This function calls 3 other functions:
  - validate_password
  - create_session
  - log_audit_event

This function is called by 5 other functions:
  - login
  - api_authenticate
  - refresh_token
  ...

File imports 8 modules:
  - bcrypt, jwt, datetime
```

**Analyze Specific File:**
```
💬 You: file src/auth/handler.py

🤖 Assistant:
**File: src/auth/handler.py**
Language: python

Imports 8 modules:
  - bcrypt
  - jwt
  - datetime
  ...

Contains 12 functions/classes:
  - authenticate_user
  - create_session
  ...

Depends on 3 other files:
  - src/models/user.py
  - src/utils/crypto.py
```

**Find Similar Implementations:**
```
💬 You: similar password validation logic

🤖 Assistant:
I found 4 similar implementations:

1. **validate_password** in `src/auth/validator.py`
   Lines of code: 23
   Similarity: 92.15%

2. **check_password_strength** in `src/utils/security.py`
   Lines of code: 45
   Similarity: 78.43%

Insights:
  Average lines: 31.5
  Most concise: validate_password (23 lines)
```

**Other Commands:**
- `history` - Show conversation history
- `clear` - Clear conversation history
- `exit` or `quit` - Exit chat mode

#### Example Questions You Can Ask

**Understanding Code:**
- "How does user authentication work?"
- "Explain the request flow through the system"
- "What does the ingest_repository function do?"

**Finding Code:**
- "Where is database connection handled?"
- "Show me all validation functions"
- "Find API endpoint definitions"

**Dependencies & Relationships:**
- "What calls the login function?"
- "What files depend on user.py?"
- "Show me the import chain for this module"

**Code Quality & Patterns:**
- "Find similar error handling patterns"
- "Are there duplicate implementations of authentication?"
- "What's the most complex file?"

**Impact Analysis:**
- "What breaks if I change the authenticate_user function?"
- "What depends on the User class?"
- "Show all usages of this API endpoint"

### 6. View Graph Summary

See statistics about your interconnected code graph:

```bash
python main.py summary
```

Output:
```
Code Graph Summary
============================================================

Nodes:
  Files: 45
  Functions: 234
  Classes: 67

Relationships:
  Import relationships: 189
  Function call relationships: 456
  Uses relationships: 23
  Total: 668
```

### 7. Interactive Mode

Start an interactive session:

```bash
python main.py interactive
```

Commands in interactive mode:
- `search <query>` - Search for code
- `function <name>` - Analyze function usage
- `exit` - Exit interactive mode

## Project Structure

```
graphrag/
├── main.py                          # Main entry point
├── requirements.txt                 # Python dependencies
├── .env.example                     # Environment variables template
├── README.md                        # This file
├── ARCHITECTURE.md                  # System architecture & cross-file relationships
├── CHAT_GUIDE.md                    # Comprehensive chat usage guide
├── QUERIES.md                       # Useful Neo4j Cypher queries
└── src/
    ├── parsers/
    │   └── ast_parser.py           # Tree-sitter AST parser (extracts imports & calls)
    ├── graph/
    │   └── neo4j_handler.py        # Neo4j database handler (with relationships)
    ├── embeddings/
    │   └── embedding_handler.py    # Milvus embeddings handler
    ├── rag/
    │   ├── rag_system.py           # RAG query system
    │   └── chat_interface.py       # Conversational chat interface
    └── ingestion_pipeline.py       # Two-pass ingestion: nodes + relationships
```

## API Usage

You can also use the components programmatically:

### Using the Chat Interface

```python
from src.rag.chat_interface import CodeChatInterface

# Initialize chat (basic mode)
chat = CodeChatInterface(use_llm=False)

# Ask questions
result = chat.chat("How does authentication work?")
print(result['answer'])
print(f"Found {len(result['sources'])} relevant code sections")

# Analyze specific function
func_info = chat.ask_about_function("authenticate_user")
print(func_info['answer'])

# Analyze specific file
file_info = chat.ask_about_file("src/auth/handler.py")
print(file_info['answer'])

# Find similar implementations
similar = chat.find_similar_implementations("password validation")
print(similar['answer'])

# View conversation history
history = chat.get_conversation_history()
for entry in history:
    print(f"Q: {entry['query']}")
    print(f"A: {entry['response'][:100]}...")

chat.close()
```

### Using the RAG System Directly

```python
from src.ingestion_pipeline import CodeIngestionPipeline
from src.rag.rag_system import CodeRAGSystem

# Ingest a repository (two-pass: nodes + relationships)
pipeline = CodeIngestionPipeline()
stats = pipeline.ingest_repository('/path/to/repo', clear_existing=True)
print(f"Created {stats['import_relationships']} import relationships")
print(f"Created {stats['call_relationships']} call relationships")
pipeline.close()

# Query the codebase
rag = CodeRAGSystem()

# Semantic search
results = rag.semantic_search("authentication logic", top_k=5)

# Review code
review = rag.review_code_snippet(code_snippet, language='python')

# Analyze function with relationships
analysis = rag.analyze_function_usage('login')
print(f"Called by {analysis['usage_count']} functions")

# Compare implementations
comparison = rag.compare_implementations("sorting algorithm")

rag.close()
```

### Using Neo4j Handler for Graph Queries

```python
from src.graph.neo4j_handler import Neo4jHandler

neo4j = Neo4jHandler()

# Get function dependencies
deps = neo4j.get_function_dependencies("src/auth.py:login:45")
print(f"Calls: {[f['name'] for f in deps['calls']]}")
print(f"Called by: {len(deps['called_by'])} functions")

# Get file dependencies
file_deps = neo4j.get_file_dependencies("src/auth/handler.py")
print(f"Imports: {[m['name'] for m in file_deps['imports']]}")
print(f"Depends on {len(file_deps['dependent_files'])} files")

# Get graph summary
summary = neo4j.get_cross_file_relationships_summary()
print(f"Total relationships: {summary['call_relationships'] + summary['import_relationships']}")

neo4j.close()
```

## Supported Languages

| Language   | Extension | Status |
|------------|-----------|--------|
| Python     | .py       | ✅     |
| JavaScript | .js       | ✅     |
| TypeScript | .ts, .tsx | ✅     |
| Java       | .java     | ✅     |
| Go         | .go       | ✅     |

## Use Cases

1. **💬 Conversational Code Exploration**: Ask natural language questions about your codebase
2. **🔍 Semantic Code Search**: Find functionality by describing what it does, not just keywords
3. **🔗 Dependency Analysis**: Understand cross-file relationships, imports, and function calls
4. **💥 Impact Analysis**: See what breaks when you change a function or class
5. **🔄 Duplication Detection**: Find similar implementations and consolidation opportunities
6. **📊 Code Quality Insights**: Identify highly coupled code, unused functions, circular dependencies
7. **🎯 Code Review**: Get suggestions based on similar patterns in your codebase
8. **🗺️ Code Navigation**: Explore relationships between files, functions, and classes
9. **📈 Pattern Discovery**: Find common patterns and best practices across your codebase
10. **🚨 Refactoring Safety**: Identify all usages before making changes

## Advanced Configuration

### Custom Embedding Model

You can use different embedding models by changing the `EMBEDDING_MODEL` in `.env`:

```env
# Smaller, faster model
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

# Larger, more accurate model
EMBEDDING_MODEL=sentence-transformers/all-mpnet-base-v2

# Code-specific model
EMBEDDING_MODEL=microsoft/codebert-base
```

### Neo4j Queries

You can extend the Neo4j handler with custom queries:

```python
from graph.neo4j_handler import Neo4jHandler

neo4j = Neo4jHandler()

# Custom query
query = """
MATCH (f:Function)-[:CALLS]->(called:Function)
WHERE f.name = $function_name
RETURN called.name as called_function, called.file as file
"""

with neo4j.driver.session() as session:
    results = session.run(query, {'function_name': 'login'})
```

## Troubleshooting

### Neo4j Connection Error
- Ensure Neo4j is running: `docker ps` or check Neo4j Desktop
- Verify credentials in `.env`
- Test connection: `http://localhost:7474`

### Milvus Connection Error
- Check Milvus is running: `docker ps`
- Verify port 19530 is accessible
- Restart Milvus: `docker-compose restart`

### Tree-sitter Language Errors
- Ensure all tree-sitter language packages are installed
- Try reinstalling: `pip install --upgrade tree-sitter-python tree-sitter-javascript`

### Memory Issues
- Process large repositories in batches
- Increase Docker memory limits
- Use a more efficient embedding model

## Performance Tips

1. **Batch Processing**: The ingestion pipeline processes files in batches
2. **Indexing**: Neo4j indexes are created automatically for faster queries
3. **Vector Search**: Milvus IVF_FLAT index provides good balance of speed and accuracy
4. **Caching**: Consider caching frequently accessed embeddings

## Additional Documentation

- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Detailed architecture explanation, cross-file relationships, and extension guide
- **[CHAT_GUIDE.md](CHAT_GUIDE.md)** - Comprehensive chat interface user guide with examples
- **[QUERIES.md](QUERIES.md)** - 30+ useful Neo4j Cypher queries for code analysis

## Key Features Explained

### Cross-File Relationships

The system now creates **interconnected graphs** instead of isolated file nodes:

- **IMPORTS relationships**: Track which files import which modules
- **CALLS relationships**: Track function calls across files
- **USES relationships**: Track general dependencies
- **Two-pass ingestion**: First creates nodes, then links them with relationships

Query cross-file relationships:
```cypher
// Find all cross-file function calls
MATCH (f1:File)-[:CONTAINS]->(fn1:Function)-[:CALLS]->(fn2:Function)<-[:CONTAINS]-(f2:File)
WHERE f1.path <> f2.path
RETURN f1.path, fn1.name, f2.path, fn2.name
```

### Conversational Chat

Two modes available:

1. **Basic Mode** (No API key): Uses semantic search + graph relationships
2. **LLM Mode** (Requires OpenAI): Natural language responses powered by GPT

Both modes combine:
- Vector search in Milvus for relevant code
- Graph queries in Neo4j for relationships
- Contextual information about dependencies

## Contributing

Contributions are welcome! Areas for improvement:

- ✅ ~~Add cross-file relationship tracking~~ (Done!)
- ✅ ~~Add conversational chat interface~~ (Done!)
- Add more programming languages (Rust, C++, Ruby, etc.)
- Add code complexity metrics
- Create web UI for visualization
- Enhance LLM integration with more providers (Claude, Local LLMs)

## License

MIT License - feel free to use and modify for your needs.

## Acknowledgments

- [Tree-sitter](https://tree-sitter.github.io/tree-sitter/) for AST parsing
- [Neo4j](https://neo4j.com/) for graph database
- [Milvus](https://milvus.io/) for vector database
- [Sentence Transformers](https://www.sbert.net/) for embeddings
