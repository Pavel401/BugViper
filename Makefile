.PHONY: help setup start stop clean install test ingest search

help:
	@echo "Code Review Tool - Makefile Commands"
	@echo "===================================="
	@echo ""
	@echo "Setup & Installation:"
	@echo "  make setup      - Run setup script"
	@echo "  make install    - Install Python dependencies"
	@echo ""
	@echo "Database Management:"
	@echo "  make start      - Start Neo4j and Milvus (docker-compose)"
	@echo "  make stop       - Stop databases"
	@echo "  make restart    - Restart databases"
	@echo "  make clean      - Stop and remove all data (DESTRUCTIVE)"
	@echo ""
	@echo "Usage:"
	@echo "  make ingest REPO=/path/to/repo  - Ingest a repository"
	@echo "  make search QUERY='your query'  - Search for code"
	@echo "  make interactive                - Start interactive mode"
	@echo ""
	@echo "Development:"
	@echo "  make test       - Run tests (if available)"
	@echo "  make logs       - View database logs"
	@echo ""

setup:
	@bash setup.sh

install:
	@pip install -r requirements.txt

start:
	@echo "Starting Neo4j and Milvus..."
	@docker-compose up -d
	@echo "Waiting for services to start (30 seconds)..."
	@sleep 30
	@echo "✓ Services started"
	@echo "  Neo4j: http://localhost:7474 (neo4j/password)"
	@echo "  Milvus: localhost:19530"

stop:
	@echo "Stopping databases..."
	@docker-compose stop

restart:
	@echo "Restarting databases..."
	@docker-compose restart
	@sleep 30
	@echo "✓ Services restarted"

clean:
	@echo "⚠️  This will DELETE all data!"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		docker-compose down -v; \
		echo "✓ All data cleaned"; \
	else \
		echo "Cancelled"; \
	fi

logs:
	@docker-compose logs -f

logs-neo4j:
	@docker-compose logs -f neo4j

logs-milvus:
	@docker-compose logs -f milvus-standalone

status:
	@echo "Service Status:"
	@docker-compose ps

ingest:
ifndef REPO
	@echo "Error: REPO not specified"
	@echo "Usage: make ingest REPO=/path/to/repo"
	@exit 1
endif
	@echo "Ingesting repository: $(REPO)"
	@python main.py ingest $(REPO) --clear

search:
ifndef QUERY
	@echo "Error: QUERY not specified"
	@echo "Usage: make search QUERY='authentication function'"
	@exit 1
endif
	@python main.py search "$(QUERY)"

interactive:
	@python main.py interactive

example:
	@python examples/example_usage.py

test:
	@echo "Running tests..."
	@python -m pytest tests/ -v || echo "No tests found. Create tests/ directory with test files."

check-services:
	@echo "Checking services..."
	@curl -s http://localhost:7474 > /dev/null && echo "✓ Neo4j is running" || echo "✗ Neo4j is not responding"
	@python -c "from pymilvus import connections; connections.connect('default', 'localhost', '19530'); print('✓ Milvus is running')" 2>/dev/null || echo "✗ Milvus is not responding"

quick-start:
	@echo "Quick Start - Setting up everything..."
	@make start
	@make install
	@make check-services
	@echo ""
	@echo "✓ Setup complete!"
	@echo ""
	@echo "Next: make ingest REPO=/path/to/your/code"
