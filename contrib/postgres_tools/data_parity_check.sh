#!/bin/bash

# SPDX-License-Identifier: GPL-2.0-or-later
# Data Parity Check Script for MySQL to PostgreSQL Conversion
# This script compares table row counts between MySQL and PostgreSQL databases
# to verify the converter produces identical data.

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Database credentials
DB_USER="${DB_USER:-trinity}"
DB_PASSWORD="${DB_PASSWORD:-trinity}"

# MySQL ports (3.3.5 branch)
MYSQL_AUTH_PORT="${MYSQL_AUTH_PORT:-33506}"
MYSQL_CHAR_PORT="${MYSQL_CHAR_PORT:-33507}"
MYSQL_WORLD_PORT="${MYSQL_WORLD_PORT:-33508}"

# PostgreSQL ports (3.3.5 branch)
POSTGRES_AUTH_PORT="${POSTGRES_AUTH_PORT:-53556}"
POSTGRES_CHAR_PORT="${POSTGRES_CHAR_PORT:-53557}"
POSTGRES_WORLD_PORT="${POSTGRES_WORLD_PORT:-53558}"

# TDB location
TDB_PATH="${TDB_PATH:-$HOME/Repos/github.com/wowemulation-dev/TDB/335/25101_2025_10_21/TDB_full_world_335.25101_2025_10_21.sql}"

# Output directory
OUTPUT_DIR="${PROJECT_ROOT}/data_parity_results"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

function log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

function log_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

function log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

function log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

function show_usage() {
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  full           Run full parity check (setup, import, count, compare)"
    echo "  setup          Set up database containers only"
    echo "  import-mysql   Import MySQL databases"
    echo "  import-pg      Import PostgreSQL databases"
    echo "  convert        Convert MySQL SQL files to PostgreSQL"
    echo "  count-mysql    Collect MySQL table counts"
    echo "  count-pg       Collect PostgreSQL table counts"
    echo "  compare        Compare counts and show differences"
    echo "  cleanup        Remove containers and temp files"
    echo ""
    echo "Environment variables:"
    echo "  TDB_PATH       Path to TDB world SQL file"
    echo "  DB_USER        Database user (default: trinity)"
    echo "  DB_PASSWORD    Database password (default: trinity)"
}

function wait_for_mysql() {
    local port=$1
    local db=$2
    local max_attempts=30
    local attempt=0

    while [ $attempt -lt $max_attempts ]; do
        if mysql -h 127.0.0.1 -P "$port" -u "$DB_USER" -p"$DB_PASSWORD" -e "SELECT 1" "$db" &>/dev/null; then
            return 0
        fi
        attempt=$((attempt + 1))
        sleep 1
    done
    return 1
}

function wait_for_postgres() {
    local port=$1
    local db=$2
    local max_attempts=30
    local attempt=0

    while [ $attempt -lt $max_attempts ]; do
        if PGPASSWORD="$DB_PASSWORD" psql -h 127.0.0.1 -p "$port" -U "$DB_USER" -d "$db" -c "SELECT 1" &>/dev/null; then
            return 0
        fi
        attempt=$((attempt + 1))
        sleep 1
    done
    return 1
}

function setup_containers() {
    log_info "Setting up database containers..."
    cd "$PROJECT_ROOT"
    ./test-dev-environment.sh setup-containers

    log_info "Waiting for MySQL containers to be ready..."
    wait_for_mysql "$MYSQL_AUTH_PORT" "trinity_auth" || { log_error "MySQL auth not ready"; exit 1; }
    wait_for_mysql "$MYSQL_CHAR_PORT" "trinity_characters" || { log_error "MySQL characters not ready"; exit 1; }
    wait_for_mysql "$MYSQL_WORLD_PORT" "trinity_world" || { log_error "MySQL world not ready"; exit 1; }

    log_info "Waiting for PostgreSQL containers to be ready..."
    wait_for_postgres "$POSTGRES_AUTH_PORT" "trinity_auth" || { log_error "PostgreSQL auth not ready"; exit 1; }
    wait_for_postgres "$POSTGRES_CHAR_PORT" "trinity_characters" || { log_error "PostgreSQL characters not ready"; exit 1; }
    wait_for_postgres "$POSTGRES_WORLD_PORT" "trinity_world" || { log_error "PostgreSQL world not ready"; exit 1; }

    log_success "All containers ready"
}

function import_mysql() {
    log_info "Importing MySQL databases..."

    # Auth database
    log_info "Importing auth database..."
    mysql -h 127.0.0.1 -P "$MYSQL_AUTH_PORT" -u "$DB_USER" -p"$DB_PASSWORD" trinity_auth < "$PROJECT_ROOT/sql/base/auth_database.sql"
    log_success "Auth database imported"

    # Characters database
    log_info "Importing characters database..."
    mysql -h 127.0.0.1 -P "$MYSQL_CHAR_PORT" -u "$DB_USER" -p"$DB_PASSWORD" trinity_characters < "$PROJECT_ROOT/sql/base/characters_database.sql"
    log_success "Characters database imported"

    # World database (TDB)
    log_info "Importing world database (this takes several minutes)..."
    if [ -f "$TDB_PATH" ]; then
        mysql -h 127.0.0.1 -P "$MYSQL_WORLD_PORT" -u "$DB_USER" -p"$DB_PASSWORD" trinity_world < "$TDB_PATH"
        log_success "World database imported"
    else
        log_error "TDB file not found: $TDB_PATH"
        exit 1
    fi
}

function convert_sql() {
    log_info "Converting MySQL SQL files to PostgreSQL..."

    mkdir -p "$PROJECT_ROOT/sql/base/postgresql"

    cd "$SCRIPT_DIR"

    # Ensure uv is available
    if ! command -v uv &> /dev/null; then
        log_error "uv is not installed. Install it from https://docs.astral.sh/uv/"
        exit 1
    fi

    # Sync dependencies if needed
    uv sync --quiet

    # Convert auth database
    log_info "Converting auth database..."
    uv run mysql-to-postgres \
        "$PROJECT_ROOT/sql/base/auth_database.sql" \
        "$PROJECT_ROOT/sql/base/postgresql/auth_database.sql"
    log_success "Auth database converted"

    # Convert characters database
    log_info "Converting characters database..."
    uv run mysql-to-postgres \
        "$PROJECT_ROOT/sql/base/characters_database.sql" \
        "$PROJECT_ROOT/sql/base/postgresql/characters_database.sql"
    log_success "Characters database converted"

    # Convert world database (TDB)
    log_info "Converting world database (this takes several minutes)..."
    if [ -f "$TDB_PATH" ]; then
        uv run mysql-to-postgres \
            "$TDB_PATH" \
            "$PROJECT_ROOT/sql/base/postgresql/TDB_full_world_335.sql" \
            --debug
        log_success "World database converted"
    else
        log_error "TDB file not found: $TDB_PATH"
        exit 1
    fi
}

function reset_postgres_db() {
    local port=$1
    local db=$2

    PGPASSWORD="$DB_PASSWORD" psql -h 127.0.0.1 -p "$port" -U "$DB_USER" -d postgres -c "
        SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$db' AND pid <> pg_backend_pid();
    " &>/dev/null || true

    PGPASSWORD="$DB_PASSWORD" psql -h 127.0.0.1 -p "$port" -U "$DB_USER" -d postgres -c "DROP DATABASE IF EXISTS $db;" &>/dev/null
    PGPASSWORD="$DB_PASSWORD" psql -h 127.0.0.1 -p "$port" -U "$DB_USER" -d postgres -c "CREATE DATABASE $db OWNER $DB_USER;" &>/dev/null
}

function import_postgres() {
    log_info "Importing PostgreSQL databases..."

    # Reset and import auth database
    log_info "Resetting and importing auth database..."
    reset_postgres_db "$POSTGRES_AUTH_PORT" "trinity_auth"
    PGPASSWORD="$DB_PASSWORD" psql -h 127.0.0.1 -p "$POSTGRES_AUTH_PORT" -U "$DB_USER" -d trinity_auth \
        < "$PROJECT_ROOT/sql/base/postgresql/auth_database.sql"
    log_success "Auth database imported"

    # Reset and import characters database
    log_info "Resetting and importing characters database..."
    reset_postgres_db "$POSTGRES_CHAR_PORT" "trinity_characters"
    PGPASSWORD="$DB_PASSWORD" psql -h 127.0.0.1 -p "$POSTGRES_CHAR_PORT" -U "$DB_USER" -d trinity_characters \
        < "$PROJECT_ROOT/sql/base/postgresql/characters_database.sql"
    log_success "Characters database imported"

    # Reset and import world database
    log_info "Resetting and importing world database (this takes several minutes)..."
    reset_postgres_db "$POSTGRES_WORLD_PORT" "trinity_world"
    PGPASSWORD="$DB_PASSWORD" psql -h 127.0.0.1 -p "$POSTGRES_WORLD_PORT" -U "$DB_USER" -d trinity_world \
        < "$PROJECT_ROOT/sql/base/postgresql/TDB_full_world_335.sql" 2>&1 | grep -v "^NOTICE:" || true
    log_success "World database imported"
}

function count_mysql_tables() {
    local port=$1
    local db=$2
    local output_file=$3

    mysql -h 127.0.0.1 -P "$port" -u "$DB_USER" -p"$DB_PASSWORD" -N -e "
        SELECT table_name, table_rows
        FROM information_schema.tables
        WHERE table_schema = '$db'
        ORDER BY table_name
    " "$db" > "$output_file"
}

function count_mysql_tables_exact() {
    local port=$1
    local db=$2
    local output_file=$3

    # Get list of tables
    tables=$(mysql -h 127.0.0.1 -P "$port" -u "$DB_USER" -p"$DB_PASSWORD" -N -e "
        SELECT table_name FROM information_schema.tables WHERE table_schema = '$db' ORDER BY table_name
    " "$db")

    echo -n "" > "$output_file"
    for table in $tables; do
        count=$(mysql -h 127.0.0.1 -P "$port" -u "$DB_USER" -p"$DB_PASSWORD" -N -e "SELECT COUNT(*) FROM \`$table\`" "$db" 2>/dev/null || echo "0")
        echo "$table,$count" >> "$output_file"
    done
}

function count_postgres_tables() {
    local port=$1
    local db=$2
    local output_file=$3

    PGPASSWORD="$DB_PASSWORD" psql -h 127.0.0.1 -p "$port" -U "$DB_USER" -d "$db" -t -A -F',' -c "
        SELECT tablename,
               (xpath('/row/cnt/text()', query_to_xml(format('SELECT COUNT(*) as cnt FROM %I', tablename), false, true, '')))[1]::text::bigint as count
        FROM pg_tables
        WHERE schemaname = 'public'
        ORDER BY tablename
    " > "$output_file"
}

function collect_mysql_counts() {
    log_info "Collecting MySQL table counts..."

    mkdir -p "$OUTPUT_DIR"

    log_info "Counting auth tables (exact)..."
    count_mysql_tables_exact "$MYSQL_AUTH_PORT" "trinity_auth" "$OUTPUT_DIR/mysql_auth_counts.csv"

    log_info "Counting characters tables (exact)..."
    count_mysql_tables_exact "$MYSQL_CHAR_PORT" "trinity_characters" "$OUTPUT_DIR/mysql_characters_counts.csv"

    log_info "Counting world tables (exact - this takes a while)..."
    count_mysql_tables_exact "$MYSQL_WORLD_PORT" "trinity_world" "$OUTPUT_DIR/mysql_world_counts.csv"

    log_success "MySQL counts saved to $OUTPUT_DIR/mysql_*_counts.csv"
}

function collect_postgres_counts() {
    log_info "Collecting PostgreSQL table counts..."

    mkdir -p "$OUTPUT_DIR"

    log_info "Counting auth tables..."
    count_postgres_tables "$POSTGRES_AUTH_PORT" "trinity_auth" "$OUTPUT_DIR/pg_auth_counts.csv"

    log_info "Counting characters tables..."
    count_postgres_tables "$POSTGRES_CHAR_PORT" "trinity_characters" "$OUTPUT_DIR/pg_characters_counts.csv"

    log_info "Counting world tables..."
    count_postgres_tables "$POSTGRES_WORLD_PORT" "trinity_world" "$OUTPUT_DIR/pg_world_counts.csv"

    log_success "PostgreSQL counts saved to $OUTPUT_DIR/pg_*_counts.csv"
}

function compare_counts() {
    log_info "Comparing table counts..."

    local has_differences=0

    for db in auth characters world; do
        log_info "Comparing $db database..."

        local mysql_file="$OUTPUT_DIR/mysql_${db}_counts.csv"
        local pg_file="$OUTPUT_DIR/pg_${db}_counts.csv"
        local diff_file="$OUTPUT_DIR/diff_${db}.txt"

        if [ ! -f "$mysql_file" ] || [ ! -f "$pg_file" ]; then
            log_error "Count files not found for $db"
            continue
        fi

        # Create associative arrays for comparison
        declare -A mysql_counts
        declare -A pg_counts

        while IFS=',' read -r table count; do
            table=$(echo "$table" | tr -d '[:space:]')
            count=$(echo "$count" | tr -d '[:space:]')
            mysql_counts["$table"]="$count"
        done < "$mysql_file"

        while IFS=',' read -r table count; do
            table=$(echo "$table" | tr -d '[:space:]')
            count=$(echo "$count" | tr -d '[:space:]')
            pg_counts["$table"]="$count"
        done < "$pg_file"

        # Find differences
        echo "=== $db Database Differences ===" > "$diff_file"
        echo "" >> "$diff_file"

        local db_has_diff=0

        # Check tables in MySQL
        for table in "${!mysql_counts[@]}"; do
            mysql_count="${mysql_counts[$table]}"
            pg_count="${pg_counts[$table]:-MISSING}"

            if [ "$pg_count" = "MISSING" ]; then
                echo "MISSING IN PG: $table (MySQL: $mysql_count)" >> "$diff_file"
                db_has_diff=1
            elif [ "$mysql_count" != "$pg_count" ]; then
                diff=$((mysql_count - pg_count))
                echo "DIFF: $table | MySQL: $mysql_count | PG: $pg_count | Diff: $diff" >> "$diff_file"
                db_has_diff=1
            fi
        done

        # Check tables only in PostgreSQL
        for table in "${!pg_counts[@]}"; do
            if [ -z "${mysql_counts[$table]}" ]; then
                echo "EXTRA IN PG: $table (PG: ${pg_counts[$table]})" >> "$diff_file"
                db_has_diff=1
            fi
        done

        if [ $db_has_diff -eq 0 ]; then
            echo "All tables match!" >> "$diff_file"
            log_success "$db database: All ${#mysql_counts[@]} tables match"
        else
            has_differences=1
            log_warning "$db database: Differences found (see $diff_file)"
            cat "$diff_file"
        fi

        unset mysql_counts
        unset pg_counts
    done

    # Create summary report
    create_summary_report

    if [ $has_differences -eq 0 ]; then
        log_success "All databases have matching counts!"
        return 0
    else
        log_warning "Differences found - see $OUTPUT_DIR/summary_report.txt"
        return 1
    fi
}

function create_summary_report() {
    local report="$OUTPUT_DIR/summary_report_${TIMESTAMP}.txt"

    echo "=== Data Parity Summary Report ===" > "$report"
    echo "Generated: $(date)" >> "$report"
    echo "TDB Source: $TDB_PATH" >> "$report"
    echo "" >> "$report"

    for db in auth characters world; do
        echo "--- $db Database ---" >> "$report"

        local mysql_file="$OUTPUT_DIR/mysql_${db}_counts.csv"
        local pg_file="$OUTPUT_DIR/pg_${db}_counts.csv"

        if [ -f "$mysql_file" ]; then
            mysql_tables=$(wc -l < "$mysql_file")
            mysql_total=$(awk -F',' '{sum+=$2} END {print sum}' "$mysql_file")
            echo "MySQL: $mysql_tables tables, $mysql_total total rows" >> "$report"
        fi

        if [ -f "$pg_file" ]; then
            pg_tables=$(wc -l < "$pg_file")
            pg_total=$(awk -F',' '{sum+=$2} END {print sum}' "$pg_file")
            echo "PostgreSQL: $pg_tables tables, $pg_total total rows" >> "$report"
        fi

        if [ -f "$OUTPUT_DIR/diff_${db}.txt" ]; then
            diff_count=$(grep -c "^DIFF:\|^MISSING\|^EXTRA" "$OUTPUT_DIR/diff_${db}.txt" 2>/dev/null || echo "0")
            echo "Differences: $diff_count" >> "$report"
        fi

        echo "" >> "$report"
    done

    # Append detailed diffs
    echo "=== Detailed Differences ===" >> "$report"
    for db in auth characters world; do
        if [ -f "$OUTPUT_DIR/diff_${db}.txt" ]; then
            cat "$OUTPUT_DIR/diff_${db}.txt" >> "$report"
            echo "" >> "$report"
        fi
    done

    log_info "Summary report: $report"
}

function full_check() {
    log_info "Starting full data parity check..."
    echo ""

    setup_containers
    echo ""

    import_mysql
    echo ""

    collect_mysql_counts
    echo ""

    convert_sql
    echo ""

    import_postgres
    echo ""

    collect_postgres_counts
    echo ""

    compare_counts
}

function cleanup() {
    log_info "Cleaning up..."
    cd "$PROJECT_ROOT"
    ./test-dev-environment.sh cleanup-containers
    rm -rf "$OUTPUT_DIR"
    log_success "Cleanup complete"
}

# Main entry point
case "${1:-}" in
    full)
        full_check
        ;;
    setup)
        setup_containers
        ;;
    import-mysql)
        import_mysql
        ;;
    import-pg)
        import_postgres
        ;;
    convert)
        convert_sql
        ;;
    count-mysql)
        collect_mysql_counts
        ;;
    count-pg)
        collect_postgres_counts
        ;;
    compare)
        compare_counts
        ;;
    cleanup)
        cleanup
        ;;
    *)
        show_usage
        exit 1
        ;;
esac
