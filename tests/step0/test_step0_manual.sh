#!/bin/bash
# Manual test script for Step 0
# Run this to verify Step 0 implementation works correctly

set -e

echo "🧪 Testing Step 0 - Safety Net Implementation"
echo "=============================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test 1: Verify baseline tests exist and can run
echo "Test 1: Running baseline tests..."
if pytest tests/step0/test_baseline.py -v; then
    echo -e "${GREEN}✓ Baseline tests passed${NC}"
else
    echo -e "${RED}✗ Baseline tests failed${NC}"
    exit 1
fi
echo ""

# Test 2: Verify Step 0 tests exist and can run
echo "Test 2: Running Step 0 tests..."
if pytest tests/step0/test_step0.py -v; then
    echo -e "${GREEN}✓ Step 0 tests passed${NC}"
else
    echo -e "${RED}✗ Step 0 tests failed${NC}"
    exit 1
fi
echo ""

# Test 3: Verify CLI commands exist
echo "Test 3: Checking CLI commands..."
if rag --help | grep -q "validate"; then
    echo -e "${GREEN}✓ 'rag validate' command exists${NC}"
else
    echo -e "${RED}✗ 'rag validate' command not found${NC}"
    exit 1
fi

if rag --help | grep -q "explain"; then
    echo -e "${GREEN}✓ 'rag explain' command exists${NC}"
else
    echo -e "${RED}✗ 'rag explain' command not found${NC}"
    exit 1
fi
echo ""

# Test 4: Test validate command (may fail if Ollama not running, that's OK)
echo "Test 4: Testing 'rag validate' command..."
if rag validate 2>&1 | grep -q "Running system validation"; then
    echo -e "${GREEN}✓ 'rag validate' command runs${NC}"
    echo -e "${YELLOW}  (Note: May show errors if Ollama is not running - that's OK)${NC}"
else
    echo -e "${RED}✗ 'rag validate' command failed to run${NC}"
    exit 1
fi
echo ""

# Test 5: Test explain command (will fail if no index, that's OK)
echo "Test 5: Testing 'rag explain' command..."
if rag explain "test question" 2>&1 | head -1 | grep -q "Question:"; then
    echo -e "${GREEN}✓ 'rag explain' command runs${NC}"
    echo -e "${YELLOW}  (Note: May show errors if no index exists - that's OK)${NC}"
else
    # Check if it's the expected "no index" error
    if rag explain "test question" 2>&1 | grep -q "No index found"; then
        echo -e "${GREEN}✓ 'rag explain' command runs (correctly reports no index)${NC}"
    else
        echo -e "${RED}✗ 'rag explain' command failed unexpectedly${NC}"
        exit 1
    fi
fi
echo ""

# Test 6: Verify existing commands still work
echo "Test 6: Verifying existing commands still exist..."
for cmd in ingest index ask stats; do
    if rag --help | grep -q "$cmd"; then
        echo -e "${GREEN}✓ 'rag $cmd' command exists${NC}"
    else
        echo -e "${RED}✗ 'rag $cmd' command missing${NC}"
        exit 1
    fi
done
echo ""

echo -e "${GREEN}=============================================="
echo "✅ All Step 0 tests passed!"
echo "==============================================${NC}"
