# BugViper

![Work In Progress](https://img.shields.io/badge/Status-Work_In_Progress-orange)

BugViper is an advanced AI-powered code review and repository ingestion tool. It leverages **Tree-sitter** for precise code parsing, **Neo4j** for graph-based relationship analysis, and **AI Agents** to automate code understanding and quality checks.

## 🚀 Features

- **Deep Repository Ingestion**: Parses and maps complete codebases using Tree-sitter.
- **Graph Knowledge Base**: Stories code entities and relationships in Neo4j for complex querying.
- **AI Agents**: Automated PR analysis and code insights powered by LLMs.
- **Modern Dashboard**: Clean and responsive interface built with Next.js 15.

## 🛠️ Stack

- **Backend**: Python 3.13, FastAPI
- **Database**: Neo4j
- **Frontend**: Next.js 16, React 19, TailwindCSS 4
- **AI**: Pydantic AI, OpenAI
- **Parsing**: Tree-sitter

## 📸 Gallery

<div align="center">

### The Dashboard

Overview of the repository status and recent activities.
<br/>
<img src="./screenshots/dashboard.png" alt="Dashboard View" width="800"/>
<br/><br/>

### Knowledge Graph

Deep dive into code relationships and dependencies rooted in Neo4j.
<br/>
<img src="./screenshots/graph.png" alt="Graph View" width="800"/>
<br/><br/>

### AI Agents

Intelligent code analysis and automated PR reviews.
<br/>
<img src="./screenshots/agent.png" alt="Agent View" width="800"/>
<br/><br/>

</div>

## 🚧 Work In Progress

This project is currently under active development.

- [ ] Make the Review Model more abstract
- [ ] Improve the Code Re Indexing
- [ ] Implement Github Push, Pull, and Branch Webhooks
- [ ] Add guardrails
- [ ] Create a project specifc guidelines for the AI Agents
- [ ] Automatically tag the claude.md file
