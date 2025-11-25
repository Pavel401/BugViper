#!/bin/bash

echo "Code Review Tool Setup Script"
echo "=============================="
echo ""

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Python version: $python_version"

# Create virtual environment
echo ""
echo "Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install dependencies
echo ""
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create .env file
echo ""
if [ ! -f .env ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "✓ Created .env file. Please update with your credentials."
else
    echo "✓ .env file already exists."
fi

# Check Neo4j
echo ""
echo "Checking Neo4j..."
if command -v docker &> /dev/null; then
    neo4j_running=$(docker ps | grep neo4j)
    if [ -z "$neo4j_running" ]; then
        echo "⚠ Neo4j not detected. Start with:"
        echo "  docker run -d -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/password neo4j:latest"
    else
        echo "✓ Neo4j is running"
    fi
else
    echo "⚠ Docker not found. Install Neo4j manually or via Docker"
fi

# Check Milvus
echo ""
echo "Checking Milvus..."
if command -v docker &> /dev/null; then
    milvus_running=$(docker ps | grep milvus)
    if [ -z "$milvus_running" ]; then
        echo "⚠ Milvus not detected. Install with:"
        echo "  wget https://github.com/milvus-io/milvus/releases/download/v2.3.4/milvus-standalone-docker-compose.yml -O docker-compose.yml"
        echo "  docker-compose up -d"
    else
        echo "✓ Milvus is running"
    fi
fi

echo ""
echo "=============================="
echo "Setup complete!"
echo ""
echo "Next steps:"
echo "1. Activate virtual environment: source venv/bin/activate"
echo "2. Update .env with your Neo4j credentials"
echo "3. Ensure Neo4j and Milvus are running"
echo "4. Run: python main.py ingest /path/to/your/repo"
echo ""
