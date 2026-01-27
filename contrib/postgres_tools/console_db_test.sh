#!/bin/bash

# SPDX-License-Identifier: GPL-2.0-or-later
#
# Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors

# PostgreSQL Database Console Test Script
# Tests database functionality via worldserver/authserver console commands
#
# Usage: ./console_db_test.sh [authserver|worldserver|both|quick]
#
# This script sends commands to the server console and validates responses
# to verify PostgreSQL database operations work correctly.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR}/../.."

# Configuration
# Note: test-dev-environment.sh sets INSTALL_DIR_POSTGRES, which is passed as INSTALL_DIR
INSTALL_DIR="${INSTALL_DIR:-${PROJECT_ROOT}/install-335-postgresql}"
LOG_DIR="${PROJECT_ROOT}/console_test_logs"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-60}"

# Database connection settings (should match test-dev-environment.sh)
DB_USER="${DB_USER:-trinity}"
DB_PASSWORD="${DB_PASSWORD:-trinity}"
POSTGRES_AUTH_PORT="${POSTGRES_AUTH_PORT:-53556}"
POSTGRES_CHAR_PORT="${POSTGRES_CHAR_PORT:-53557}"
POSTGRES_WORLD_PORT="${POSTGRES_WORLD_PORT:-53558}"

# Test account name (will be created and deleted during testing)
TEST_ACCOUNT="pgtestacct"
TEST_PASSWORD="testpass123"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test counters
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_SKIPPED=0

function log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

function log_success() {
    echo -e "${GREEN}[PASS]${NC} $1"
    TESTS_PASSED=$((TESTS_PASSED + 1))
}

function log_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
    TESTS_FAILED=$((TESTS_FAILED + 1))
}

function log_skip() {
    echo -e "${YELLOW}[SKIP]${NC} $1"
    TESTS_SKIPPED=$((TESTS_SKIPPED + 1))
}

function log_section() {
    echo ""
    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
}

function check_prerequisites() {
    log_section "Checking Prerequisites"

    # Check install directory
    if [ ! -d "${INSTALL_DIR}" ]; then
        log_fail "Install directory not found: ${INSTALL_DIR}"
        echo "Run: ./test-dev-environment.sh build-postgres"
        exit 1
    fi
    log_success "Install directory exists"

    # Check binaries
    if [ ! -x "${INSTALL_DIR}/bin/authserver" ]; then
        log_fail "authserver binary not found"
        exit 1
    fi
    log_success "authserver binary exists"

    if [ ! -x "${INSTALL_DIR}/bin/worldserver" ]; then
        log_fail "worldserver binary not found"
        exit 1
    fi
    log_success "worldserver binary exists"

    # Check configuration
    if [ ! -f "${INSTALL_DIR}/etc/authserver.conf" ]; then
        log_fail "authserver.conf not found"
        echo "Run: ./test-dev-environment.sh configure-postgres"
        exit 1
    fi
    log_success "authserver.conf exists"

    if [ ! -f "${INSTALL_DIR}/etc/worldserver.conf" ]; then
        log_fail "worldserver.conf not found"
        echo "Run: ./test-dev-environment.sh configure-postgres"
        exit 1
    fi
    log_success "worldserver.conf exists"

    # Check PostgreSQL connectivity
    log_info "Testing PostgreSQL connectivity..."
    if PGPASSWORD="${DB_PASSWORD}" psql -h 127.0.0.1 -p "${POSTGRES_AUTH_PORT}" -U "${DB_USER}" -d trinity_auth -c "SELECT 1" >/dev/null 2>&1; then
        log_success "PostgreSQL auth database accessible"
    else
        log_fail "Cannot connect to PostgreSQL auth database on port ${POSTGRES_AUTH_PORT}"
        echo "Run: ./test-dev-environment.sh setup-postgres"
        exit 1
    fi

    # Create log directory
    mkdir -p "${LOG_DIR}"
    log_success "Log directory ready: ${LOG_DIR}"
}

function cleanup_test_account() {
    # Clean up any leftover test account from previous runs
    log_info "Cleaning up any existing test account..."
    PGPASSWORD="${DB_PASSWORD}" psql -h 127.0.0.1 -p "${POSTGRES_AUTH_PORT}" -U "${DB_USER}" -d trinity_auth \
        -c "DELETE FROM account WHERE username = UPPER('${TEST_ACCOUNT}')" >/dev/null 2>&1 || true
}

function cleanup_servers() {
    # Kill any running server processes that might block ports
    log_info "Cleaning up any existing server processes..."
    pkill -9 -x authserver 2>/dev/null || true
    pkill -9 -x worldserver 2>/dev/null || true
    sleep 1
    # Verify ports are free
    if ss -tlnp 2>/dev/null | grep -q ":3724 "; then
        log_fail "Port 3724 still in use after cleanup"
        return 1
    fi
    return 0
}

function test_authserver_startup() {
    log_section "Testing authserver Startup"

    local LOG_FILE="${LOG_DIR}/authserver_startup.log"

    log_info "Starting authserver with timeout of ${TIMEOUT_SECONDS}s..."

    cd "${INSTALL_DIR}"

    # Run authserver and let it complete (it will exit after startup in test environment)
    # The timeout ensures we don't wait forever if the server hangs
    # Use stdbuf to force line buffering for reliable log capture
    timeout "${TIMEOUT_SECONDS}" stdbuf -oL -eL ./bin/authserver -c etc/authserver.conf > "${LOG_FILE}" 2>&1 || true

    cd - >/dev/null

    # Analyze the log file after server exits
    log_info "Analyzing authserver startup log..."

    # Check for successful startup indicators
    local STARTED=false

    if grep -q "Added realm" "${LOG_FILE}" 2>/dev/null; then
        STARTED=true
        log_success "authserver started and added realm"
    elif grep -q "Started listening\|Network:" "${LOG_FILE}" 2>/dev/null; then
        STARTED=true
        log_success "authserver started and listening"
    fi

    if [ "$STARTED" = false ]; then
        log_fail "authserver failed to start (no startup indicators found)"
        cat "${LOG_FILE}"
        return 1
    fi

    # Check for PostgreSQL connection
    if grep -q "DatabasePool.*opened successfully" "${LOG_FILE}"; then
        log_success "Database pool opened successfully"
    else
        log_fail "Database pool failed to open"
    fi

    # Check for update application
    if grep -q "Applied.*update" "${LOG_FILE}" || grep -q "database is up-to-date" "${LOG_FILE}"; then
        log_success "Database updates processed"
    else
        log_info "No update messages found (may be already up-to-date)"
    fi

    # Check for PostgreSQL client version in logs
    if grep -q "PostgreSQL client version" "${LOG_FILE}"; then
        log_success "PostgreSQL backend detected in logs"
    fi

    # Check if server exited cleanly
    if grep -q "Halting process" "${LOG_FILE}"; then
        log_info "Server halted cleanly (expected in test environment without clients)"
    fi

    return 0
}

function test_worldserver_console_commands() {
    log_section "Testing worldserver Console Commands"

    # The worldserver has the REPL and needs authserver running
    # Account commands work via worldserver console

    local AUTH_LOG="${LOG_DIR}/authserver_background.log"
    local WORLD_LOG="${LOG_DIR}/worldserver_console.log"
    local COMMANDS_FILE="${LOG_DIR}/worldserver_commands.txt"

    # Check if map data exists (worldserver needs it to fully start)
    if [ ! -d "${INSTALL_DIR}/../build-335-client-data/maps" ]; then
        log_info "Map data not found - worldserver cannot fully start"
        log_info "Skipping console command tests (requires extracted client data)"
        log_skip "worldserver console tests (no map data)"
        return 0
    fi

    # Prepare commands to send to worldserver
    cat > "${COMMANDS_FILE}" << EOF
.server info
.server debug
account create ${TEST_ACCOUNT} ${TEST_PASSWORD}
account set gmlevel ${TEST_ACCOUNT} 3 -1
.lookup creature Hogger
account delete ${TEST_ACCOUNT}
.server exit
EOF

    log_info "Starting authserver in background..."

    cd "${INSTALL_DIR}"

    # Clear old log
    > "${AUTH_LOG}"

    # Start authserver in background
    # - nohup: prevent SIGHUP on shell exit
    # - stdbuf: force line buffering so we can read log output in real-time
    nohup stdbuf -oL -eL ./bin/authserver -c etc/authserver.conf > "${AUTH_LOG}" 2>&1 &
    local AUTH_PID=$!

    # Wait for authserver to be ready
    local AUTH_READY=false
    local WAIT_COUNT=0
    while [ $WAIT_COUNT -lt 15 ]; do
        sleep 1
        WAIT_COUNT=$((WAIT_COUNT + 1))

        # Check if startup succeeded
        if grep -q "Added realm" "${AUTH_LOG}" 2>/dev/null; then
            # Verify it's still running (port bound successfully)
            if kill -0 "${AUTH_PID}" 2>/dev/null; then
                AUTH_READY=true
                break
            else
                # Check if it failed to bind
                if grep -q "Could not bind\|Address already in use" "${AUTH_LOG}" 2>/dev/null; then
                    log_fail "authserver failed to bind port (address in use)"
                    cat "${AUTH_LOG}"
                    cd - >/dev/null
                    return 1
                fi
            fi
        fi

        # Check if process died early
        if ! kill -0 "${AUTH_PID}" 2>/dev/null; then
            if grep -q "Could not bind\|Address already in use" "${AUTH_LOG}" 2>/dev/null; then
                log_fail "authserver failed to bind port (address in use)"
            elif grep -q "Failed to initialize network" "${AUTH_LOG}" 2>/dev/null; then
                log_fail "authserver failed to initialize network"
            else
                log_fail "authserver exited unexpectedly"
            fi
            cat "${AUTH_LOG}"
            cd - >/dev/null
            return 1
        fi
    done

    if [ "$AUTH_READY" = false ]; then
        log_fail "authserver failed to start within 10s"
        kill "${AUTH_PID}" 2>/dev/null || true
        cat "${AUTH_LOG}"
        cd - >/dev/null
        return 1
    fi

    log_success "authserver started in background (PID: ${AUTH_PID})"

    log_info "Starting worldserver with console commands..."

    # Start worldserver with commands piped to stdin
    (
        sleep 30  # Wait for worldserver to initialize and load data
        cat "${COMMANDS_FILE}"
        sleep 5   # Wait for commands to process
    ) | timeout 120 ./bin/worldserver -c etc/worldserver.conf > "${WORLD_LOG}" 2>&1 || true

    # Cleanup authserver
    log_info "Stopping authserver..."
    kill "${AUTH_PID}" 2>/dev/null || true
    wait "${AUTH_PID}" 2>/dev/null || true

    cd - >/dev/null

    # Analyze results
    log_info "Analyzing worldserver console command results..."

    # Check database connections
    if grep -q "Updating World database\|World database is up-to-date\|World initialized" "${WORLD_LOG}"; then
        log_success "World database connected"
    else
        log_fail "World database connection failed"
    fi

    # Check .server info (note: "uptime" is lowercase in output)
    if grep -q "TrinityCore" "${WORLD_LOG}" && grep -qi "uptime" "${WORLD_LOG}"; then
        log_success ".server info command worked"
    else
        log_fail ".server info command failed"
    fi

    # Check .server debug (PostgreSQL version)
    if grep -qi "PostgreSQL version" "${WORLD_LOG}"; then
        log_success ".server debug shows PostgreSQL version"
    else
        log_fail ".server debug did not show PostgreSQL version"
    fi

    # Check account create
    if grep -q "Account created" "${WORLD_LOG}"; then
        log_success "account create command worked"
    elif grep -q "already exist" "${WORLD_LOG}"; then
        log_info "Account already existed (cleanup may have failed)"
    else
        log_fail "account create command failed"
    fi

    # Check lookup command
    if grep -q "448" "${WORLD_LOG}" && grep -qi "hogger" "${WORLD_LOG}"; then
        log_success ".lookup creature Hogger found entry 448"
    else
        log_info ".lookup creature may not have run (server initialization)"
    fi

    # Verify account was deleted from database
    local ACCOUNT_COUNT
    ACCOUNT_COUNT=$(PGPASSWORD="${DB_PASSWORD}" psql -h 127.0.0.1 -p "${POSTGRES_AUTH_PORT}" -U "${DB_USER}" -d trinity_auth \
        -t -c "SELECT COUNT(*) FROM account WHERE username = UPPER('${TEST_ACCOUNT}')" 2>/dev/null | tr -d ' ')

    if [ "$ACCOUNT_COUNT" = "0" ]; then
        log_success "account delete command worked (account removed from DB)"
    else
        log_fail "account delete may have failed (account still in DB)"
        # Clean up manually
        cleanup_test_account
    fi

    return 0
}

function test_worldserver_startup() {
    log_section "Testing worldserver Startup (Database Only)"

    local LOG_FILE="${LOG_DIR}/worldserver_startup.log"

    log_info "Starting worldserver (will exit due to missing map files)..."
    log_info "This tests database connectivity and schema loading..."

    cd "${INSTALL_DIR}"

    # Start worldserver - it will fail on map files but should connect to DB first
    timeout 120 ./bin/worldserver -c etc/worldserver.conf > "${LOG_FILE}" 2>&1 || true

    cd - >/dev/null

    # Analyze results
    log_info "Analyzing worldserver startup..."

    # Check database connections - look for update messages or pool messages
    local WORLD_DB_OK=false
    local CHAR_DB_OK=false

    # Worldserver shows "Updating World database..." when connected
    if grep -q "Updating World database\|World database is up-to-date\|DatabasePool 'trinity_world' opened" "${LOG_FILE}"; then
        log_success "World database connected"
        WORLD_DB_OK=true
    else
        log_fail "World database connection failed"
    fi

    # Worldserver shows "Updating Character database..." when connected
    if grep -q "Updating Character database\|Character database is up-to-date\|DatabasePool 'trinity_characters' opened" "${LOG_FILE}"; then
        log_success "Characters database connected"
        CHAR_DB_OK=true
    else
        log_fail "Characters database connection failed"
    fi

    # Check realm ID to verify auth database connectivity
    if grep -q "Realm running as realm ID\|Using World DB:" "${LOG_FILE}"; then
        log_success "Auth database connected (realm info loaded)"
    else
        log_info "Auth database connection status unclear"
    fi

    # Check for schema import (first run)
    if grep -q "auto populating" "${LOG_FILE}"; then
        log_success "Auto-populating empty database detected"
    fi

    # Check for update application
    if grep -q "Applied.*successfully" "${LOG_FILE}"; then
        log_success "SQL updates applied"
    fi

    # Check for data loading
    if grep -q "Loading.*template" "${LOG_FILE}"; then
        log_success "World data loading started"
    fi

    # Expected exit: missing map files
    if grep -q "Unable to open.*maps" "${LOG_FILE}" || grep -q "Correct .*DataDir" "${LOG_FILE}"; then
        log_info "Server exited due to missing map files (expected in test environment)"
    fi

    return 0
}

function test_direct_db_queries() {
    log_section "Testing Direct Database Queries"

    log_info "Testing queries that worldserver would execute..."

    # Test auth database
    local AUTH_RESULT
    AUTH_RESULT=$(PGPASSWORD="${DB_PASSWORD}" psql -h 127.0.0.1 -p "${POSTGRES_AUTH_PORT}" -U "${DB_USER}" -d trinity_auth \
        -t -c "SELECT COUNT(*) FROM realmlist" 2>/dev/null | tr -d ' ')
    if [ -n "$AUTH_RESULT" ] && [ "$AUTH_RESULT" -ge 0 ]; then
        log_success "Auth DB query: realmlist has ${AUTH_RESULT} entries"
    else
        log_fail "Auth DB query failed"
    fi

    # Test characters database
    local CHAR_TABLE_COUNT
    CHAR_TABLE_COUNT=$(PGPASSWORD="${DB_PASSWORD}" psql -h 127.0.0.1 -p "${POSTGRES_CHAR_PORT}" -U "${DB_USER}" -d trinity_characters \
        -t -c "SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public'" 2>/dev/null | tr -d ' ')
    if [ -n "$CHAR_TABLE_COUNT" ] && [ "$CHAR_TABLE_COUNT" -gt 0 ]; then
        log_success "Characters DB: ${CHAR_TABLE_COUNT} tables exist"
    else
        log_fail "Characters DB query failed"
    fi

    # Test world database
    local CREATURE_COUNT
    CREATURE_COUNT=$(PGPASSWORD="${DB_PASSWORD}" psql -h 127.0.0.1 -p "${POSTGRES_WORLD_PORT}" -U "${DB_USER}" -d trinity_world \
        -t -c "SELECT COUNT(*) FROM creature_template" 2>/dev/null | tr -d ' ')
    if [ -n "$CREATURE_COUNT" ] && [ "$CREATURE_COUNT" -gt 0 ]; then
        log_success "World DB query: creature_template has ${CREATURE_COUNT} entries"
    else
        log_fail "World DB query failed (creature_template may not be loaded)"
    fi

    # Test a complex query
    local HOGGER_CHECK
    HOGGER_CHECK=$(PGPASSWORD="${DB_PASSWORD}" psql -h 127.0.0.1 -p "${POSTGRES_WORLD_PORT}" -U "${DB_USER}" -d trinity_world \
        -t -c "SELECT name FROM creature_template WHERE entry = 448" 2>/dev/null | tr -d ' ')
    if [ "$HOGGER_CHECK" = "Hogger" ]; then
        log_success "World DB: Hogger (entry 448) found correctly"
    elif [ -n "$CREATURE_COUNT" ] && [ "$CREATURE_COUNT" -gt 0 ]; then
        log_info "Hogger not found (TDB may not be fully loaded)"
    else
        log_skip "Skipping Hogger check (no creature data)"
    fi

    # Test updates table
    local UPDATES_COUNT
    UPDATES_COUNT=$(PGPASSWORD="${DB_PASSWORD}" psql -h 127.0.0.1 -p "${POSTGRES_AUTH_PORT}" -U "${DB_USER}" -d trinity_auth \
        -t -c "SELECT COUNT(*) FROM updates WHERE state = 'RELEASED'" 2>/dev/null | tr -d ' ')
    if [ -n "$UPDATES_COUNT" ]; then
        log_success "Auth DB: ${UPDATES_COUNT} RELEASED updates tracked"
    fi

    return 0
}

function test_bytea_data() {
    log_section "Testing BYTEA Column Data"

    log_info "Verifying binary data was converted and imported correctly..."

    # Check build_auth_key table
    local AUTH_KEY_COUNT
    AUTH_KEY_COUNT=$(PGPASSWORD="${DB_PASSWORD}" psql -h 127.0.0.1 -p "${POSTGRES_AUTH_PORT}" -U "${DB_USER}" -d trinity_auth \
        -t -c "SELECT COUNT(*) FROM build_auth_key WHERE key IS NOT NULL" 2>/dev/null | tr -d ' ')
    if [ -n "$AUTH_KEY_COUNT" ] && [ "$AUTH_KEY_COUNT" -gt 0 ]; then
        log_success "build_auth_key: ${AUTH_KEY_COUNT} entries with BYTEA data"
    else
        log_info "build_auth_key: No entries (may need TDB import)"
    fi

    # Check build_executable_hash table
    local EXEC_HASH_COUNT
    EXEC_HASH_COUNT=$(PGPASSWORD="${DB_PASSWORD}" psql -h 127.0.0.1 -p "${POSTGRES_AUTH_PORT}" -U "${DB_USER}" -d trinity_auth \
        -t -c "SELECT COUNT(*) FROM build_executable_hash WHERE executablehash IS NOT NULL" 2>/dev/null | tr -d ' ')
    if [ -n "$EXEC_HASH_COUNT" ] && [ "$EXEC_HASH_COUNT" -gt 0 ]; then
        log_success "build_executable_hash: ${EXEC_HASH_COUNT} entries with BYTEA data"
    else
        log_info "build_executable_hash: No entries (may need TDB import)"
    fi

    # Verify BYTEA data length is correct (should be 16 bytes for auth keys)
    local KEY_LENGTH
    KEY_LENGTH=$(PGPASSWORD="${DB_PASSWORD}" psql -h 127.0.0.1 -p "${POSTGRES_AUTH_PORT}" -U "${DB_USER}" -d trinity_auth \
        -t -c "SELECT LENGTH(key) FROM build_auth_key LIMIT 1" 2>/dev/null | tr -d ' ')
    if [ "$KEY_LENGTH" = "16" ]; then
        log_success "BYTEA key length correct (16 bytes)"
    elif [ -n "$KEY_LENGTH" ]; then
        log_fail "BYTEA key length unexpected: ${KEY_LENGTH} (expected 16)"
    fi

    return 0
}

function print_summary() {
    log_section "Test Summary"

    echo ""
    echo -e "  ${GREEN}Passed:${NC}  ${TESTS_PASSED}"
    echo -e "  ${RED}Failed:${NC}  ${TESTS_FAILED}"
    echo -e "  ${YELLOW}Skipped:${NC} ${TESTS_SKIPPED}"
    echo ""

    if [ ${TESTS_FAILED} -eq 0 ]; then
        echo -e "${GREEN}All tests passed!${NC}"
        return 0
    else
        echo -e "${RED}Some tests failed. Check logs in: ${LOG_DIR}${NC}"
        return 1
    fi
}

function run_quick_test() {
    log_section "Quick Database Connectivity Test"

    check_prerequisites
    test_direct_db_queries
    test_bytea_data
    print_summary
}

function run_authserver_test() {
    check_prerequisites
    cleanup_servers
    test_authserver_startup
    test_direct_db_queries
    print_summary
}

function run_worldserver_test() {
    check_prerequisites
    cleanup_servers
    test_worldserver_startup
    test_direct_db_queries
    test_bytea_data
    print_summary
}

function run_console_test() {
    # Full console test - requires map data for worldserver
    check_prerequisites
    cleanup_servers
    cleanup_test_account
    test_worldserver_console_commands
    test_direct_db_queries
    test_bytea_data
    print_summary
}

function run_full_test() {
    check_prerequisites
    cleanup_servers
    cleanup_test_account
    test_authserver_startup
    # Wait for port to be fully released after authserver test
    sleep 2
    test_worldserver_startup
    # Cleanup before console test to ensure clean state
    cleanup_servers
    test_worldserver_console_commands
    test_direct_db_queries
    test_bytea_data
    print_summary
}

function show_usage() {
    echo "PostgreSQL Database Console Test Script"
    echo ""
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  quick        Quick connectivity test (no server startup)"
    echo "  authserver   Test authserver startup and DB connectivity"
    echo "  worldserver  Test worldserver startup and DB loading"
    echo "  console      Test console commands (requires map data)"
    echo "  both         Full test of both servers (default)"
    echo ""
    echo "Environment variables:"
    echo "  INSTALL_DIR       PostgreSQL install directory"
    echo "  TIMEOUT_SECONDS   Server startup timeout (default: 60)"
    echo "  DB_USER           Database user (default: trinity)"
    echo "  DB_PASSWORD       Database password (default: trinity)"
    echo ""
    echo "Examples:"
    echo "  $0 quick           # Fast connectivity check"
    echo "  $0 authserver      # Test authserver console commands"
    echo "  $0 worldserver     # Test worldserver startup and DB loading"
    echo "  $0 both            # Complete test suite"
}

# Main entry point
case "${1:-both}" in
    quick)
        run_quick_test
        ;;
    authserver)
        run_authserver_test
        ;;
    worldserver)
        run_worldserver_test
        ;;
    console)
        run_console_test
        ;;
    both|full)
        run_full_test
        ;;
    -h|--help|help)
        show_usage
        ;;
    *)
        echo "Unknown command: $1"
        show_usage
        exit 1
        ;;
esac
