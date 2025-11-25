# Chat with Your Codebase - User Guide

## Overview

The Chat interface allows you to have **conversational interactions** with your codebase using natural language. It combines semantic search, graph relationships, and optional LLM enhancement to answer questions about your code.

## Quick Start

### 1. Basic Chat Mode (No LLM Required)

```bash
python main.py chat
```

This uses semantic search + graph relationships to answer questions. Works offline, no API keys needed.

### 2. AI-Enhanced Chat Mode (Requires OpenAI API)

```bash
python main.py chat --llm
```

This uses GPT-4 or GPT-3.5 to generate natural, context-aware responses.

**Setup:**
```bash
# Add to .env file
OPENAI_API_KEY=your_api_key_here
```

Or export as environment variable:
```bash
export OPENAI_API_KEY=your_api_key_here
python main.py chat --llm
```

## How to Use

### Ask Questions

Simply type your question in natural language:

```
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
   ...
```

### Special Commands

#### Analyze a Function
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
  ...
```

#### Analyze a File
```
💬 You: file src/auth/handler.py

🤖 Assistant:
**File: src/auth/handler.py**
Language: python
Name: handler.py

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
  ...
```

#### Find Similar Implementations
```
💬 You: similar user validation logic

🤖 Assistant:
I found 3 similar implementations:

1. **validate_user_input** in `src/validators/user.py`
   Language: python
   Lines of code: 45
   Similarity: 91.25%

2. **check_user_data** in `src/api/validators.py`
   ...
```

#### View Conversation History
```
💬 You: history

📜 Conversation History (3 exchanges):

1. Q: How does authentication work?
   A: I found 5 relevant code sections...

2. Q: function authenticate_user
   A: **Function: authenticate_user**...

3. Q: What about password hashing?
   A: I found 3 relevant code sections...
```

#### Clear History
```
💬 You: clear
✓ Conversation history cleared.
```

#### Exit
```
💬 You: exit
Goodbye! 👋
```

## Example Conversations

### Understanding Code Flow

```
💬 You: How does a user request flow through the system?

🤖 Assistant:
Based on the codebase, I found the main request flow:

1. **handle_request** in `src/api/server.py` receives incoming requests
2. It calls **route_request** in `src/api/router.py` to determine the handler
3. Request goes through middleware in `src/middleware/auth.py`
4. Finally reaches specific handlers in `src/handlers/` directory

The main entry point has 12 different functions calling it.
```

### Finding Usage Examples

```
💬 You: Show me examples of database queries

🤖 Assistant:
I found 8 code sections with database queries:

1. **fetch_users** (function) in `src/db/queries.py`
   Preview: def fetch_users(filters): return db.session.query(User)...

2. **get_user_by_id** (function) in `src/models/user.py`
   ...

Most common pattern: Using SQLAlchemy ORM queries
```

### Debugging and Investigation

```
💬 You: Where is error handling for API requests?

🤖 Assistant:
I found 4 relevant sections for error handling:

1. **handle_api_error** (function) in `src/api/error_handler.py`
   Location: Line 23-56
   This handles all API exceptions

2. **exception_middleware** (function) in `src/middleware/exceptions.py`
   This catches unhandled exceptions

3. **log_error** (function) in `src/utils/logger.py`
   Called by: handle_api_error, exception_middleware
```

### Code Quality Analysis

```
💬 You: similar error handling patterns

🤖 Assistant:
I found 6 similar implementations:

Insights:
  Average lines: 34.5
  Most concise: simple_error_handler (18 lines)

This suggests there might be opportunity to consolidate error handling
into a single, reusable pattern.
```

## Tips for Better Results

### 1. Be Specific
❌ "Show me functions"
✅ "How is user authentication implemented?"

### 2. Use Domain Terms
Include terminology from your codebase:
- Function names
- Class names
- Module names
- Technical concepts

### 3. Ask About Relationships
- "What calls function X?"
- "What does file Y depend on?"
- "How are modules A and B connected?"

### 4. Iterate and Refine
If the first answer isn't what you need, rephrase:
```
💬 You: How does authentication work?
🤖 [Shows general auth code]

💬 You: Specifically, how are JWT tokens validated?
🤖 [Shows JWT-specific code]
```

### 5. Use Commands for Precise Queries
When you know exactly what you want:
- `function <name>` - Direct function analysis
- `file <path>` - Direct file analysis
- `similar <description>` - Find similar patterns

## How It Works

### Basic Mode (No LLM)

1. **Semantic Search**: Your question is converted to an embedding
2. **Vector Search**: Milvus finds the most similar code chunks
3. **Graph Enrichment**: Neo4j adds relationship context
4. **Response Generation**: Formats results with file locations, similarity scores, and relationships

### LLM-Enhanced Mode

1-3. Same as basic mode
4. **LLM Processing**: GPT analyzes the code chunks
5. **Natural Response**: Generates conversational, context-aware answers with explanations

## Comparison: Basic vs LLM Mode

| Feature | Basic Mode | LLM Mode |
|---------|------------|----------|
| Response Style | Structured list | Natural language |
| Code Explanation | File + line numbers | Explains what code does |
| Relationships | Shows count | Explains significance |
| Insights | Lists matches | Suggests improvements |
| API Key Required | ❌ No | ✅ Yes (OpenAI) |
| Cost | Free | ~$0.001-0.01 per query |
| Speed | Fast (~1-2s) | Moderate (~3-5s) |

## Advanced Usage

### Programmatic Access

```python
from src.rag.chat_interface import CodeChatInterface

# Initialize chat
chat = CodeChatInterface(use_llm=True)

# Ask a question
result = chat.chat("How does authentication work?")
print(result['answer'])

# Show sources
for source in result['sources']:
    print(f"{source['file_path']}:{source['start_line']}")

# Analyze specific function
func_info = chat.ask_about_function("authenticate_user")
print(func_info['answer'])

# Analyze specific file
file_info = chat.ask_about_file("src/auth/handler.py")
print(file_info['answer'])

# Clean up
chat.close()
```

### Custom LLM Integration

The system supports OpenAI by default, but you can modify `chat_interface.py` to use:
- Anthropic Claude
- Azure OpenAI
- Local LLMs (Ollama, LM Studio)
- Any OpenAI-compatible API

## Troubleshooting

### "No results found"
- Make sure you've ingested the repository: `python main.py ingest .`
- Check if Neo4j and Milvus are running
- Try rephrasing your question

### "LLM integration failed"
- Check `OPENAI_API_KEY` is set correctly
- Verify you have credits in your OpenAI account
- System will fall back to basic mode automatically

### Slow responses
- Basic mode: Check Milvus connection
- LLM mode: GPT-4 is slower than GPT-3.5, edit `chat_interface.py` line 123 to use `gpt-3.5-turbo`

### Wrong or irrelevant results
- The semantic search works best with specific terminology
- Try using exact function/class names
- Use `function` or `file` commands for precise queries

## Best Practices

1. **Ingest First**: Always ingest your repo before chatting
2. **Start Broad, Then Narrow**: Begin with general questions, then drill down
3. **Check Sources**: Use "Show source files?" to verify accuracy
4. **Use History**: Reference previous answers with `history` command
5. **Iterate**: If the answer isn't helpful, rephrase and try again

## What Can You Ask?

### Code Understanding
- "How does [feature] work?"
- "What does [function] do?"
- "Explain the authentication flow"

### Finding Code
- "Where is error handling implemented?"
- "Show me database query functions"
- "Find API endpoint definitions"

### Relationships
- "What calls this function?"
- "What files depend on this module?"
- "Show me the dependency chain"

### Patterns & Quality
- "Find similar validation logic"
- "Are there duplicate implementations?"
- "What's the most complex file?"

### Impact Analysis
- "What breaks if I change this function?"
- "What depends on this class?"
- "Show me all callers of this API"

## Integration with Other Tools

The chat interface works seamlessly with:
- Neo4j Browser (for graph visualization)
- Your IDE (copy file paths directly)
- CI/CD (programmatic API for automated analysis)

## Next Steps

1. Try the basic chat: `python main.py chat`
2. Experiment with questions about your codebase
3. Set up OpenAI API for enhanced responses
4. Integrate into your development workflow
5. Build custom tools using the `CodeChatInterface` API

Happy chatting with your code! 🚀
