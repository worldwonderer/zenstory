#!/bin/bash
# Unified quality checker
# Usage: ./scripts/quality/check-quality.sh [all|backend|frontend|security|i18n]

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

CHECK="${1:-all}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Print usage
print_usage() {
    echo "Usage: $0 [all|backend|frontend|security|i18n]"
    echo ""
    echo "Check types:"
    echo "  all       - Run all checks (backend + frontend, default)"
    echo "  backend   - Ruff, MyPy, Bandit, Safety"
    echo "  frontend  - CSS token, ESLint, TypeScript check"
    echo "  security  - Bandit + Safety (security focused)"
    echo "  i18n      - Hardcoded Chinese text detection"
}

# Backend quality checks
check_backend() {
    echo -e "\n${BLUE}======================================${NC}"
    echo -e "${BLUE}     Backend Quality Checks${NC}"
    echo -e "${BLUE}======================================${NC}\n"

    cd "$PROJECT_ROOT/apps/server"

    # Activate virtual environment if exists
    if [ -d "venv" ]; then
        source venv/bin/activate
    else
        echo -e "${YELLOW}Warning: Virtual environment not found at apps/server/venv${NC}"
        echo -e "${YELLOW}Some checks may fail. Run: cd apps/server && python3 -m venv venv && pip install -r requirements.txt${NC}\n"
    fi

    # 1. Ruff - Python linting
    echo -e "${YELLOW}1. Ruff (Python linting)...${NC}"
    if command -v ruff &> /dev/null; then
        ruff check agent/ api/ services/ || {
            echo -e "${RED}Ruff check failed${NC}"
            return 1
        }
        echo -e "${GREEN}Ruff check passed${NC}\n"
    else
        echo -e "${YELLOW}Ruff not installed. Skip with warning.${NC}\n"
    fi

    # 2. MyPy - Type checking
    echo -e "${YELLOW}2. MyPy (Type checking)...${NC}"
    if command -v mypy &> /dev/null; then
        mypy agent/ api/ --ignore-missing-imports || {
            echo -e "${RED}MyPy check failed${NC}"
            return 1
        }
        echo -e "${GREEN}MyPy check passed${NC}\n"
    else
        echo -e "${YELLOW}MyPy not installed. Skip with warning.${NC}\n"
    fi

    # 3. Bandit - Security linting
    echo -e "${YELLOW}3. Bandit (Security linting)...${NC}"
    if command -v bandit &> /dev/null; then
        bandit -r agent/ api/ -ll || {
            echo -e "${RED}Bandit check failed${NC}"
            return 1
        }
        echo -e "${GREEN}Bandit check passed${NC}\n"
    else
        echo -e "${YELLOW}Bandit not installed. Skip with warning.${NC}\n"
    fi

    # 4. Safety - Dependency vulnerabilities
    echo -e "${YELLOW}4. Safety (Dependency vulnerabilities)...${NC}"
    if command -v safety &> /dev/null; then
        safety check --short || {
            echo -e "${RED}Safety check failed${NC}"
            return 1
        }
        echo -e "${GREEN}Safety check passed${NC}\n"
    else
        echo -e "${YELLOW}Safety not installed. Skip with warning.${NC}\n"
    fi

    cd "$PROJECT_ROOT"
    echo -e "${GREEN}Backend quality checks completed!${NC}"
}

# Frontend quality checks
check_frontend() {
    echo -e "\n${BLUE}======================================${NC}"
    echo -e "${BLUE}     Frontend Quality Checks${NC}"
    echo -e "${BLUE}======================================${NC}\n"

    cd "$PROJECT_ROOT/apps/web"

    # Check if node_modules exists
    if [ ! -d "node_modules" ]; then
        echo -e "${YELLOW}Warning: node_modules not found. Run: cd apps/web && pnpm install${NC}\n"
    fi

    # 1. CSS token variable consistency
    echo -e "${YELLOW}1. CSS token variable consistency...${NC}"
    pnpm lint:tokens || {
        echo -e "${RED}CSS token check failed${NC}"
        return 1
    }
    echo -e "${GREEN}CSS token check passed${NC}\n"

    # 2. ESLint
    echo -e "${YELLOW}2. ESLint (JavaScript/TypeScript linting)...${NC}"
    pnpm lint || {
        echo -e "${RED}ESLint check failed${NC}"
        return 1
    }
    echo -e "${GREEN}ESLint check passed${NC}\n"

    # 3. TypeScript check
    echo -e "${YELLOW}3. TypeScript (Type checking)...${NC}"
    pnpm exec tsc --noEmit || {
        echo -e "${RED}TypeScript check failed${NC}"
        return 1
    }
    echo -e "${GREEN}TypeScript check passed${NC}\n"

    cd "$PROJECT_ROOT"
    echo -e "${GREEN}Frontend quality checks completed!${NC}"
}

# Security checks (Bandit + Safety)
check_security() {
    echo -e "\n${BLUE}======================================${NC}"
    echo -e "${BLUE}        Security Checks${NC}"
    echo -e "${BLUE}======================================${NC}\n"

    cd "$PROJECT_ROOT/apps/server"

    # Activate virtual environment if exists
    if [ -d "venv" ]; then
        source venv/bin/activate
    fi

    # 1. Bandit - Security linting
    echo -e "${YELLOW}1. Bandit (Security linting)...${NC}"
    if command -v bandit &> /dev/null; then
        bandit -r agent/ api/ -ll || {
            echo -e "${RED}Bandit check failed${NC}"
            return 1
        }
        echo -e "${GREEN}Bandit check passed${NC}\n"
    else
        echo -e "${YELLOW}Bandit not installed. Skip with warning.${NC}\n"
    fi

    # 2. Safety - Dependency vulnerabilities
    echo -e "${YELLOW}2. Safety (Dependency vulnerabilities)...${NC}"
    if command -v safety &> /dev/null; then
        safety check --short || {
            echo -e "${RED}Safety check failed${NC}"
            return 1
        }
        echo -e "${GREEN}Safety check passed${NC}\n"
    else
        echo -e "${YELLOW}Safety not installed. Skip with warning.${NC}\n"
    fi

    cd "$PROJECT_ROOT"
    echo -e "${GREEN}Security checks completed!${NC}"
}

# i18n checks (Hardcoded Chinese text)
check_i18n() {
    echo -e "\n${BLUE}======================================${NC}"
    echo -e "${BLUE}        i18n Checks${NC}"
    echo -e "${BLUE}======================================${NC}\n"

    echo -e "${YELLOW}Detecting hardcoded Chinese text in apps/web/src...${NC}\n"

    FOUND_ISSUES=0

    # Find all .tsx and .ts files
    # Exclude node_modules, .d.ts files
    # Use grep with Perl regex to match Chinese characters
    find "$PROJECT_ROOT/apps/web/src" -type f \( -name "*.tsx" -o -name "*.ts" \) ! -path "*/node_modules/*" ! -name "*.d.ts" | while read file; do
        # Check for Chinese characters
        # Exclude:
        # - Comment lines (//)
        # - Lines with useTranslation
        # - Lines with t(' or t("
        # - Lines with i18n
        # - Lines with getLocale
        # - Import statements
        result=$(grep -n -P "[\x{4e00}-\x{9fa5}]" "$file" 2>/dev/null | \
            grep -v "^\s*//" | \
            grep -v "useTranslation" | \
            grep -vE "t\(['\"]" | \
            grep -v "i18n" | \
            grep -v "getLocale" | \
            grep -v "^\s*import")

        if [ -n "$result" ]; then
            echo -e "${YELLOW}File: $file${NC}"
            echo "$result"
            echo ""
            FOUND_ISSUES=1
        fi
    done

    echo -e "${BLUE}======================================${NC}"
    if [ "$FOUND_ISSUES" -eq 0 ]; then
        echo -e "${GREEN}No hardcoded Chinese text found!${NC}"
    else
        echo -e "${YELLOW}Please review the results above for potential i18n issues.${NC}"
        echo -e "${YELLOW}Note: Some results may be false positives (e.g., template variables).${NC}"
    fi
}

# Main logic
echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}    Unified Quality Checker${NC}"
echo -e "${BLUE}======================================${NC}"

case "$CHECK" in
    all)
        check_backend && check_frontend
        ;;
    backend)
        check_backend
        ;;
    frontend)
        check_frontend
        ;;
    security)
        check_security
        ;;
    i18n)
        check_i18n
        ;;
    -h|--help|help)
        print_usage
        exit 0
        ;;
    *)
        echo -e "${RED}Unknown check type: $CHECK${NC}\n"
        print_usage
        exit 1
        ;;
esac

echo -e "\n${GREEN}======================================${NC}"
echo -e "${GREEN}   All requested checks completed!${NC}"
echo -e "${GREEN}======================================${NC}"
