#!/bin/bash
# Script to run Sarah AI tests with proper setup

set -e

echo "🧪 Sarah AI Test Runner"
echo "======================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check prerequisites
echo -e "\n${YELLOW}Checking prerequisites...${NC}"

# Check PostgreSQL
if command -v psql &> /dev/null; then
    echo -e "${GREEN}✓${NC} PostgreSQL found"
else
    echo -e "${RED}✗${NC} PostgreSQL not found. Please install PostgreSQL."
    exit 1
fi

# Check Redis
if command -v redis-cli &> /dev/null; then
    echo -e "${GREEN}✓${NC} Redis found"
else
    echo -e "${RED}✗${NC} Redis not found. Please install Redis."
    exit 1
fi

# Check Python
if command -v python3 &> /dev/null; then
    echo -e "${GREEN}✓${NC} Python found"
else
    echo -e "${RED}✗${NC} Python 3 not found. Please install Python 3.11+."
    exit 1
fi

# Parse command line arguments
TEST_TYPE=${1:-all}
COVERAGE=${2:-no}

# Setup test database
echo -e "\n${YELLOW}Setting up test database...${NC}"
createdb sarah_test 2>/dev/null || echo "Test database already exists"

# Run tests based on type
echo -e "\n${YELLOW}Running tests...${NC}"

case $TEST_TYPE in
    unit)
        echo "Running unit tests only..."
        if [ "$COVERAGE" = "coverage" ]; then
            pytest -m "not integration and not performance" --cov=sarah --cov-report=term-missing
        else
            pytest -m "not integration and not performance" -v
        fi
        ;;
    integration)
        echo "Running integration tests..."
        if [ "$COVERAGE" = "coverage" ]; then
            pytest -m integration --cov=sarah --cov-report=term-missing
        else
            pytest -m integration -v
        fi
        ;;
    performance)
        echo "Running performance tests..."
        pytest -m performance -v -s
        ;;
    all)
        echo "Running all tests..."
        if [ "$COVERAGE" = "coverage" ]; then
            pytest --cov=sarah --cov-report=html --cov-report=term-missing
        else
            pytest -v
        fi
        ;;
    *)
        echo "Usage: $0 [unit|integration|performance|all] [coverage]"
        echo "  unit        - Run unit tests only"
        echo "  integration - Run integration tests"
        echo "  performance - Run performance tests"
        echo "  all         - Run all tests (default)"
        echo "  coverage    - Add as second argument to generate coverage report"
        exit 1
        ;;
esac

# Check exit code
if [ $? -eq 0 ]; then
    echo -e "\n${GREEN}✓ Tests passed!${NC}"
    
    # Show coverage report location if generated
    if [ "$COVERAGE" = "coverage" ] && [ -d "htmlcov" ]; then
        echo -e "\n${YELLOW}Coverage report generated:${NC}"
        echo "  Open htmlcov/index.html to view detailed coverage"
    fi
else
    echo -e "\n${RED}✗ Tests failed!${NC}"
    exit 1
fi