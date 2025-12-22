#!/bin/bash

# SPDX-License-Identifier: GPL-2.0-or-later
#
# Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors

# TrinityCore Development Test Environment Manager (3.3.5 WotLK)
# This script manages podman containers and test installations for dual database backend testing

set -e

# Branch-specific defaults to avoid collisions when working on multiple branches
# 3.3.5: containers trinity-335-{mysql,postgres}-*, ports MySQL 335xx, PostgreSQL 535xx
CONTAINER_PREFIX="${CONTAINER_PREFIX:-trinity-335}"

# MySQL containers
MYSQL_AUTH_CONTAINER="${CONTAINER_PREFIX}-mysql-auth"
MYSQL_CHAR_CONTAINER="${CONTAINER_PREFIX}-mysql-characters"
MYSQL_WORLD_CONTAINER="${CONTAINER_PREFIX}-mysql-world"
MYSQL_VERSION="${MYSQL_VERSION:-8}"

# PostgreSQL containers
POSTGRES_AUTH_CONTAINER="${CONTAINER_PREFIX}-postgres-auth"
POSTGRES_CHAR_CONTAINER="${CONTAINER_PREFIX}-postgres-characters"
POSTGRES_WORLD_CONTAINER="${CONTAINER_PREFIX}-postgres-world"
POSTGRES_VERSION="${POSTGRES_VERSION:-16}"

# Common settings
DB_USER="${DB_USER:-trinity}"
DB_PASSWORD="${DB_PASSWORD:-trinity}"

# MySQL ports: auth=33506, characters=33507, world=33508
MYSQL_AUTH_PORT="${MYSQL_AUTH_PORT:-33506}"
MYSQL_CHAR_PORT="${MYSQL_CHAR_PORT:-33507}"
MYSQL_WORLD_PORT="${MYSQL_WORLD_PORT:-33508}"

# PostgreSQL ports: auth=53556, characters=53557, world=53558
POSTGRES_AUTH_PORT="${POSTGRES_AUTH_PORT:-53556}"
POSTGRES_CHAR_PORT="${POSTGRES_CHAR_PORT:-53557}"
POSTGRES_WORLD_PORT="${POSTGRES_WORLD_PORT:-53558}"

# Build directories
BUILD_DIR="${BUILD_DIR:-build-335}"
BUILD_DIR_POSTGRES="${BUILD_DIR_POSTGRES:-build-335-postgres}"
INSTALL_DIR="${INSTALL_DIR:-$(pwd)/install-335}"
INSTALL_DIR_POSTGRES="${INSTALL_DIR_POSTGRES:-$(pwd)/install-335-postgres}"

MYSQL_CONTAINERS=(
    "${MYSQL_AUTH_CONTAINER}"
    "${MYSQL_CHAR_CONTAINER}"
    "${MYSQL_WORLD_CONTAINER}"
)

POSTGRES_CONTAINERS=(
    "${POSTGRES_AUTH_CONTAINER}"
    "${POSTGRES_CHAR_CONTAINER}"
    "${POSTGRES_WORLD_CONTAINER}"
)

ALL_CONTAINERS=("${MYSQL_CONTAINERS[@]}" "${POSTGRES_CONTAINERS[@]}")

function show_usage() {
    echo "Usage: $0 [command]"
    echo ""
    echo "Container Commands:"
    echo "  setup-containers       Create and start all database containers (MySQL + PostgreSQL)"
    echo "  setup-mysql            Create and start MySQL containers only"
    echo "  setup-postgres         Create and start PostgreSQL containers only"
    echo "  start-containers       Start existing containers"
    echo "  stop-containers        Stop running containers"
    echo "  cleanup-containers     Stop and remove all database containers"
    echo "  reset-databases        Drop and recreate all databases (empty state)"
    echo ""
    echo "Build Commands:"
    echo "  build                  Build TrinityCore with MySQL backend"
    echo "  build-postgres         Build TrinityCore with PostgreSQL backend"
    echo "  build-all              Build both MySQL and PostgreSQL versions"
    echo "  configure              Create MySQL configuration files"
    echo "  configure-postgres     Create PostgreSQL configuration files"
    echo ""
    echo "Test Commands:"
    echo "  test                   Test MySQL backend (start authserver briefly)"
    echo "  test-postgres          Test PostgreSQL backend"
    echo "  test-both              Test both backends sequentially"
    echo "  convert-sql            Convert SQL update files to PostgreSQL format"
    echo ""
    echo "Status/Cleanup:"
    echo "  status                 Show container and build status"
    echo "  cleanup-all            Full cleanup (containers + builds)"
    echo ""
    echo "Environment variables:"
    echo "  CONTAINER_PREFIX       Container name prefix (default: trinity-335)"
    echo "  MYSQL_VERSION          MySQL image version (default: 8)"
    echo "  POSTGRES_VERSION       PostgreSQL image version (default: 16)"
    echo "  DB_USER                Database user (default: trinity)"
    echo "  DB_PASSWORD            Database password (default: trinity)"
    echo "  BUILD_DIR              MySQL build directory (default: build-335)"
    echo "  BUILD_DIR_POSTGRES     PostgreSQL build directory (default: build-335-postgres)"
    echo "  INSTALL_DIR            MySQL install directory (default: ./install-335)"
    echo "  INSTALL_DIR_POSTGRES   PostgreSQL install directory (default: ./install-335-postgres)"
    echo ""
    echo "Databases (3.3.5 WotLK):"
    echo "  auth       - Login/authentication database"
    echo "               MySQL: port ${MYSQL_AUTH_PORT}, PostgreSQL: port ${POSTGRES_AUTH_PORT}"
    echo "  characters - Character data database"
    echo "               MySQL: port ${MYSQL_CHAR_PORT}, PostgreSQL: port ${POSTGRES_CHAR_PORT}"
    echo "  world      - World content database"
    echo "               MySQL: port ${MYSQL_WORLD_PORT}, PostgreSQL: port ${POSTGRES_WORLD_PORT}"
    echo ""
}

function setup_mysql() {
    echo "Setting up MySQL database containers..."

    # MySQL container for auth database
    if ! podman container exists "${MYSQL_AUTH_CONTAINER}"; then
        echo "Creating MySQL container for auth database (port ${MYSQL_AUTH_PORT})..."
        podman run -d --name "${MYSQL_AUTH_CONTAINER}" \
            -e MYSQL_ROOT_PASSWORD="${DB_PASSWORD}" \
            -e MYSQL_USER="${DB_USER}" \
            -e MYSQL_PASSWORD="${DB_PASSWORD}" \
            -e MYSQL_DATABASE=trinity_auth \
            -p "${MYSQL_AUTH_PORT}:3306" \
            "mysql:${MYSQL_VERSION}"
    else
        echo "Container ${MYSQL_AUTH_CONTAINER} already exists"
        podman start "${MYSQL_AUTH_CONTAINER}" 2>/dev/null || true
    fi

    # MySQL container for characters database
    if ! podman container exists "${MYSQL_CHAR_CONTAINER}"; then
        echo "Creating MySQL container for characters database (port ${MYSQL_CHAR_PORT})..."
        podman run -d --name "${MYSQL_CHAR_CONTAINER}" \
            -e MYSQL_ROOT_PASSWORD="${DB_PASSWORD}" \
            -e MYSQL_USER="${DB_USER}" \
            -e MYSQL_PASSWORD="${DB_PASSWORD}" \
            -e MYSQL_DATABASE=trinity_characters \
            -p "${MYSQL_CHAR_PORT}:3306" \
            "mysql:${MYSQL_VERSION}"
    else
        echo "Container ${MYSQL_CHAR_CONTAINER} already exists"
        podman start "${MYSQL_CHAR_CONTAINER}" 2>/dev/null || true
    fi

    # MySQL container for world database
    if ! podman container exists "${MYSQL_WORLD_CONTAINER}"; then
        echo "Creating MySQL container for world database (port ${MYSQL_WORLD_PORT})..."
        podman run -d --name "${MYSQL_WORLD_CONTAINER}" \
            -e MYSQL_ROOT_PASSWORD="${DB_PASSWORD}" \
            -e MYSQL_USER="${DB_USER}" \
            -e MYSQL_PASSWORD="${DB_PASSWORD}" \
            -e MYSQL_DATABASE=trinity_world \
            -p "${MYSQL_WORLD_PORT}:3306" \
            "mysql:${MYSQL_VERSION}"
    else
        echo "Container ${MYSQL_WORLD_CONTAINER} already exists"
        podman start "${MYSQL_WORLD_CONTAINER}" 2>/dev/null || true
    fi

    echo "Waiting for MySQL containers to be ready..."
    sleep 10

    echo ""
    echo "MySQL containers ready:"
    echo "  Auth:       localhost:${MYSQL_AUTH_PORT} (database: trinity_auth)"
    echo "  Characters: localhost:${MYSQL_CHAR_PORT} (database: trinity_characters)"
    echo "  World:      localhost:${MYSQL_WORLD_PORT} (database: trinity_world)"
    echo "  User:       ${DB_USER}"
    echo "  Password:   ${DB_PASSWORD}"
}

function setup_postgres() {
    echo "Setting up PostgreSQL database containers..."

    # PostgreSQL container for auth database
    if ! podman container exists "${POSTGRES_AUTH_CONTAINER}"; then
        echo "Creating PostgreSQL container for auth database (port ${POSTGRES_AUTH_PORT})..."
        podman run -d --name "${POSTGRES_AUTH_CONTAINER}" \
            -e POSTGRES_USER="${DB_USER}" \
            -e POSTGRES_PASSWORD="${DB_PASSWORD}" \
            -e POSTGRES_DB=trinity_auth \
            -p "${POSTGRES_AUTH_PORT}:5432" \
            "postgres:${POSTGRES_VERSION}"
    else
        echo "Container ${POSTGRES_AUTH_CONTAINER} already exists"
        podman start "${POSTGRES_AUTH_CONTAINER}" 2>/dev/null || true
    fi

    # PostgreSQL container for characters database
    if ! podman container exists "${POSTGRES_CHAR_CONTAINER}"; then
        echo "Creating PostgreSQL container for characters database (port ${POSTGRES_CHAR_PORT})..."
        podman run -d --name "${POSTGRES_CHAR_CONTAINER}" \
            -e POSTGRES_USER="${DB_USER}" \
            -e POSTGRES_PASSWORD="${DB_PASSWORD}" \
            -e POSTGRES_DB=trinity_characters \
            -p "${POSTGRES_CHAR_PORT}:5432" \
            "postgres:${POSTGRES_VERSION}"
    else
        echo "Container ${POSTGRES_CHAR_CONTAINER} already exists"
        podman start "${POSTGRES_CHAR_CONTAINER}" 2>/dev/null || true
    fi

    # PostgreSQL container for world database
    if ! podman container exists "${POSTGRES_WORLD_CONTAINER}"; then
        echo "Creating PostgreSQL container for world database (port ${POSTGRES_WORLD_PORT})..."
        podman run -d --name "${POSTGRES_WORLD_CONTAINER}" \
            -e POSTGRES_USER="${DB_USER}" \
            -e POSTGRES_PASSWORD="${DB_PASSWORD}" \
            -e POSTGRES_DB=trinity_world \
            -p "${POSTGRES_WORLD_PORT}:5432" \
            "postgres:${POSTGRES_VERSION}"
    else
        echo "Container ${POSTGRES_WORLD_CONTAINER} already exists"
        podman start "${POSTGRES_WORLD_CONTAINER}" 2>/dev/null || true
    fi

    echo "Waiting for PostgreSQL containers to be ready..."
    sleep 10

    echo ""
    echo "PostgreSQL containers ready:"
    echo "  Auth:       localhost:${POSTGRES_AUTH_PORT} (database: trinity_auth)"
    echo "  Characters: localhost:${POSTGRES_CHAR_PORT} (database: trinity_characters)"
    echo "  World:      localhost:${POSTGRES_WORLD_PORT} (database: trinity_world)"
    echo "  User:       ${DB_USER}"
    echo "  Password:   ${DB_PASSWORD}"
}

function setup_containers() {
    setup_mysql
    setup_postgres
}

function start_containers() {
    echo "Starting database containers..."
    for container in "${ALL_CONTAINERS[@]}"; do
        if podman container exists "${container}"; then
            echo "Starting ${container}..."
            podman start "${container}" || true
        else
            echo "Container ${container} does not exist. Run 'setup-containers' first."
        fi
    done
}

function stop_containers() {
    echo "Stopping database containers..."
    for container in "${ALL_CONTAINERS[@]}"; do
        if podman container exists "${container}"; then
            echo "Stopping ${container}..."
            podman stop "${container}" || true
        fi
    done
}

function cleanup_containers() {
    echo "Cleaning up database containers..."
    for container in "${ALL_CONTAINERS[@]}"; do
        if podman container exists "${container}"; then
            echo "Stopping and removing ${container}..."
            podman stop "${container}" 2>/dev/null || true
            podman rm "${container}" 2>/dev/null || true
        fi
    done
    echo "Containers removed"
}

function reset_mysql_databases() {
    echo "Resetting MySQL databases to empty state..."

    # Reset auth database
    if podman container exists "${MYSQL_AUTH_CONTAINER}"; then
        echo "Resetting MySQL auth database..."
        podman exec "${MYSQL_AUTH_CONTAINER}" mysql -u "${DB_USER}" -p"${DB_PASSWORD}" -e "
            DROP DATABASE IF EXISTS trinity_auth;
            CREATE DATABASE trinity_auth;" 2>/dev/null || echo "Warning: Could not reset MySQL auth database"
    fi

    # Reset characters database
    if podman container exists "${MYSQL_CHAR_CONTAINER}"; then
        echo "Resetting MySQL characters database..."
        podman exec "${MYSQL_CHAR_CONTAINER}" mysql -u "${DB_USER}" -p"${DB_PASSWORD}" -e "
            DROP DATABASE IF EXISTS trinity_characters;
            CREATE DATABASE trinity_characters;" 2>/dev/null || echo "Warning: Could not reset MySQL characters database"
    fi

    # Reset world database
    if podman container exists "${MYSQL_WORLD_CONTAINER}"; then
        echo "Resetting MySQL world database..."
        podman exec "${MYSQL_WORLD_CONTAINER}" mysql -u "${DB_USER}" -p"${DB_PASSWORD}" -e "
            DROP DATABASE IF EXISTS trinity_world;
            CREATE DATABASE trinity_world;" 2>/dev/null || echo "Warning: Could not reset MySQL world database"
    fi
}

function reset_postgres_databases() {
    echo "Resetting PostgreSQL databases to empty state..."

    # Reset auth database
    if podman container exists "${POSTGRES_AUTH_CONTAINER}"; then
        echo "Resetting PostgreSQL auth database..."
        podman exec "${POSTGRES_AUTH_CONTAINER}" psql -U "${DB_USER}" -d postgres -c "
            DROP DATABASE IF EXISTS trinity_auth;
            CREATE DATABASE trinity_auth OWNER ${DB_USER};" 2>/dev/null || echo "Warning: Could not reset PostgreSQL auth database"
    fi

    # Reset characters database
    if podman container exists "${POSTGRES_CHAR_CONTAINER}"; then
        echo "Resetting PostgreSQL characters database..."
        podman exec "${POSTGRES_CHAR_CONTAINER}" psql -U "${DB_USER}" -d postgres -c "
            DROP DATABASE IF EXISTS trinity_characters;
            CREATE DATABASE trinity_characters OWNER ${DB_USER};" 2>/dev/null || echo "Warning: Could not reset PostgreSQL characters database"
    fi

    # Reset world database
    if podman container exists "${POSTGRES_WORLD_CONTAINER}"; then
        echo "Resetting PostgreSQL world database..."
        podman exec "${POSTGRES_WORLD_CONTAINER}" psql -U "${DB_USER}" -d postgres -c "
            DROP DATABASE IF EXISTS trinity_world;
            CREATE DATABASE trinity_world OWNER ${DB_USER};" 2>/dev/null || echo "Warning: Could not reset PostgreSQL world database"
    fi
}

function reset_databases() {
    reset_mysql_databases
    reset_postgres_databases
    echo "All databases reset complete"
}

function build() {
    echo "Building TrinityCore (MySQL backend)..."

    mkdir -p "${BUILD_DIR}"

    cmake -S . -B "${BUILD_DIR}" \
        -DCMAKE_BUILD_TYPE=Debug \
        -DCMAKE_INSTALL_PREFIX="${INSTALL_DIR}" \
        -DWITH_WARNINGS=ON \
        -DWITH_COREDEBUG=ON \
        -DBUILD_TESTING=ON \
        -DUSE_COREPCH=ON \
        -DUSE_SCRIPTPCH=ON \
        -DSERVERS=ON \
        -DTOOLS=ON \
        -DSCRIPTS=static

    cmake --build "${BUILD_DIR}" -j "$(nproc)"
    cmake --install "${BUILD_DIR}"

    # Create configuration files
    configure
}

function build_postgres() {
    echo "Building TrinityCore (PostgreSQL backend)..."

    # Ensure PostgreSQL SQL files are converted
    convert_sql

    mkdir -p "${BUILD_DIR_POSTGRES}"

    cmake -S . -B "${BUILD_DIR_POSTGRES}" \
        -DCMAKE_BUILD_TYPE=Debug \
        -DCMAKE_INSTALL_PREFIX="${INSTALL_DIR_POSTGRES}" \
        -DWITH_WARNINGS=ON \
        -DWITH_COREDEBUG=ON \
        -DBUILD_TESTING=ON \
        -DUSE_COREPCH=ON \
        -DUSE_SCRIPTPCH=ON \
        -DSERVERS=ON \
        -DTOOLS=ON \
        -DSCRIPTS=static \
        -DWITH_POSTGRESQL=ON

    cmake --build "${BUILD_DIR_POSTGRES}" -j "$(nproc)"
    cmake --install "${BUILD_DIR_POSTGRES}"

    # Create configuration files
    configure_postgres
}

function build_all() {
    echo "Building both MySQL and PostgreSQL versions..."
    build
    build_postgres
    echo "Both builds completed"
}

function configure() {
    echo "Creating MySQL configuration files..."

    if [ ! -d "${INSTALL_DIR}/etc" ]; then
        echo "Install directory not found. Run 'build' first."
        return 1
    fi

    # Copy dist files if configs don't exist
    if [ ! -f "${INSTALL_DIR}/etc/authserver.conf" ]; then
        cp "${INSTALL_DIR}/etc/authserver.conf.dist" "${INSTALL_DIR}/etc/authserver.conf"
    fi
    if [ ! -f "${INSTALL_DIR}/etc/worldserver.conf" ]; then
        cp "${INSTALL_DIR}/etc/worldserver.conf.dist" "${INSTALL_DIR}/etc/worldserver.conf"
    fi

    # Update authserver configuration
    sed -i "s|^LoginDatabaseInfo = .*|LoginDatabaseInfo = \"127.0.0.1;${MYSQL_AUTH_PORT};${DB_USER};${DB_PASSWORD};trinity_auth\"|" \
        "${INSTALL_DIR}/etc/authserver.conf"
    sed -i 's|^Updates.EnableDatabases = .*|Updates.EnableDatabases = 1|' \
        "${INSTALL_DIR}/etc/authserver.conf"
    sed -i 's|^MySQLExecutable = .*|MySQLExecutable = "/usr/bin/mysql"|' \
        "${INSTALL_DIR}/etc/authserver.conf"

    # Update worldserver configuration
    sed -i "s|^LoginDatabaseInfo = .*|LoginDatabaseInfo = \"127.0.0.1;${MYSQL_AUTH_PORT};${DB_USER};${DB_PASSWORD};trinity_auth\"|" \
        "${INSTALL_DIR}/etc/worldserver.conf"
    sed -i "s|^CharacterDatabaseInfo = .*|CharacterDatabaseInfo = \"127.0.0.1;${MYSQL_CHAR_PORT};${DB_USER};${DB_PASSWORD};trinity_characters\"|" \
        "${INSTALL_DIR}/etc/worldserver.conf"
    sed -i "s|^WorldDatabaseInfo = .*|WorldDatabaseInfo = \"127.0.0.1;${MYSQL_WORLD_PORT};${DB_USER};${DB_PASSWORD};trinity_world\"|" \
        "${INSTALL_DIR}/etc/worldserver.conf"

    # Enable auto-updates for characters (2) + world (4) = 6, but not auth (handled by authserver)
    sed -i 's|^Updates.EnableDatabases = .*|Updates.EnableDatabases = 6|' \
        "${INSTALL_DIR}/etc/worldserver.conf"
    sed -i 's|^MySQLExecutable = .*|MySQLExecutable = "/usr/bin/mysql"|' \
        "${INSTALL_DIR}/etc/worldserver.conf"

    echo "MySQL configuration files created in ${INSTALL_DIR}/etc/"
}

function configure_postgres() {
    echo "Creating PostgreSQL configuration files..."

    if [ ! -d "${INSTALL_DIR_POSTGRES}/etc" ]; then
        echo "PostgreSQL install directory not found. Run 'build-postgres' first."
        return 1
    fi

    # Copy dist files if configs don't exist
    if [ ! -f "${INSTALL_DIR_POSTGRES}/etc/authserver.conf" ]; then
        cp "${INSTALL_DIR_POSTGRES}/etc/authserver.conf.dist" "${INSTALL_DIR_POSTGRES}/etc/authserver.conf"
    fi
    if [ ! -f "${INSTALL_DIR_POSTGRES}/etc/worldserver.conf" ]; then
        cp "${INSTALL_DIR_POSTGRES}/etc/worldserver.conf.dist" "${INSTALL_DIR_POSTGRES}/etc/worldserver.conf"
    fi

    # Update authserver configuration for PostgreSQL
    sed -i "s|^LoginDatabaseInfo = .*|LoginDatabaseInfo = \"127.0.0.1;${POSTGRES_AUTH_PORT};${DB_USER};${DB_PASSWORD};trinity_auth\"|" \
        "${INSTALL_DIR_POSTGRES}/etc/authserver.conf"
    sed -i 's|^Updates.EnableDatabases = .*|Updates.EnableDatabases = 1|' \
        "${INSTALL_DIR_POSTGRES}/etc/authserver.conf"

    # Update worldserver configuration for PostgreSQL
    sed -i "s|^LoginDatabaseInfo = .*|LoginDatabaseInfo = \"127.0.0.1;${POSTGRES_AUTH_PORT};${DB_USER};${DB_PASSWORD};trinity_auth\"|" \
        "${INSTALL_DIR_POSTGRES}/etc/worldserver.conf"
    sed -i "s|^CharacterDatabaseInfo = .*|CharacterDatabaseInfo = \"127.0.0.1;${POSTGRES_CHAR_PORT};${DB_USER};${DB_PASSWORD};trinity_characters\"|" \
        "${INSTALL_DIR_POSTGRES}/etc/worldserver.conf"
    sed -i "s|^WorldDatabaseInfo = .*|WorldDatabaseInfo = \"127.0.0.1;${POSTGRES_WORLD_PORT};${DB_USER};${DB_PASSWORD};trinity_world\"|" \
        "${INSTALL_DIR_POSTGRES}/etc/worldserver.conf"

    # Enable auto-updates for characters (2) + world (4) = 6, but not auth (handled by authserver)
    sed -i 's|^Updates.EnableDatabases = .*|Updates.EnableDatabases = 6|' \
        "${INSTALL_DIR_POSTGRES}/etc/worldserver.conf"

    # Disable console for automated testing
    sed -i 's|^Console.Enable = .*|Console.Enable = 0|' \
        "${INSTALL_DIR_POSTGRES}/etc/worldserver.conf"

    echo "PostgreSQL configuration files created in ${INSTALL_DIR_POSTGRES}/etc/"
}

function test_server() {
    echo "Testing MySQL backend..."

    if [ ! -d "${INSTALL_DIR}" ]; then
        echo "Installation not found. Run 'build' first."
        exit 1
    fi

    if [ ! -f "${INSTALL_DIR}/etc/authserver.conf" ]; then
        echo "Configuration not found. Run 'configure' first."
        exit 1
    fi

    echo "Starting authserver for testing..."
    cd "${INSTALL_DIR}"

    # Run authserver with timeout to test startup
    timeout 30 ./bin/authserver -c etc/authserver.conf &
    AUTH_PID=$!
    sleep 5

    if kill -0 "${AUTH_PID}" 2>/dev/null; then
        echo "MySQL authserver started successfully"
        kill "${AUTH_PID}" 2>/dev/null || true
        wait "${AUTH_PID}" 2>/dev/null || true
        cd - >/dev/null
        return 0
    else
        echo "MySQL authserver failed to start"
        cd - >/dev/null
        return 1
    fi
}

function test_postgres() {
    echo "Testing PostgreSQL backend..."

    if [ ! -d "${INSTALL_DIR_POSTGRES}" ]; then
        echo "PostgreSQL installation not found. Run 'build-postgres' first."
        exit 1
    fi

    if [ ! -f "${INSTALL_DIR_POSTGRES}/etc/authserver.conf" ]; then
        echo "PostgreSQL configuration not found. Run 'configure-postgres' first."
        exit 1
    fi

    echo "Starting PostgreSQL authserver for testing..."
    cd "${INSTALL_DIR_POSTGRES}"

    # Run authserver with timeout to test startup
    timeout 30 ./bin/authserver -c etc/authserver.conf &
    AUTH_PID=$!
    sleep 5

    if kill -0 "${AUTH_PID}" 2>/dev/null; then
        echo "PostgreSQL authserver started successfully"
        kill "${AUTH_PID}" 2>/dev/null || true
        wait "${AUTH_PID}" 2>/dev/null || true
        cd - >/dev/null
        return 0
    else
        echo "PostgreSQL authserver failed to start"
        cd - >/dev/null
        return 1
    fi
}

function test_both() {
    echo "Testing both MySQL and PostgreSQL backends..."

    echo ""
    echo "=== Testing MySQL Backend ==="
    if test_server; then
        echo "MySQL backend: PASSED"
    else
        echo "MySQL backend: FAILED"
    fi

    echo ""
    echo "=== Testing PostgreSQL Backend ==="
    if test_postgres; then
        echo "PostgreSQL backend: PASSED"
    else
        echo "PostgreSQL backend: FAILED"
    fi

    echo ""
    echo "=== Both tests completed ==="
}

function convert_sql() {
    echo "Converting SQL update files to PostgreSQL format..."

    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    CONVERTER="${SCRIPT_DIR}/contrib/postgres_tools/convert_all_updates.sh"

    if [ ! -f "${CONVERTER}" ]; then
        echo "Error: PostgreSQL converter not found at ${CONVERTER}"
        echo "Make sure contrib/postgres_tools/ is set up correctly."
        exit 1
    fi

    # Run the batch converter
    bash "${CONVERTER}"

    echo "SQL conversion complete"
}

function show_status() {
    echo "=== Container Status ==="
    if command -v podman &>/dev/null; then
        echo "MySQL containers:"
        podman ps -a --filter "name=${CONTAINER_PREFIX}-mysql" --format "  {{.Names}}\t{{.Status}}\t{{.Ports}}"
        echo ""
        echo "PostgreSQL containers:"
        podman ps -a --filter "name=${CONTAINER_PREFIX}-postgres" --format "  {{.Names}}\t{{.Status}}\t{{.Ports}}"
    else
        echo "podman not found"
    fi

    echo ""
    echo "=== Build Status ==="
    echo "MySQL:"
    if [ -d "${BUILD_DIR}" ]; then
        echo "  Build directory: ${BUILD_DIR} (exists)"
    else
        echo "  Build directory: ${BUILD_DIR} (missing)"
    fi
    if [ -d "${INSTALL_DIR}" ]; then
        echo "  Install directory: ${INSTALL_DIR} (exists)"
        [ -f "${INSTALL_DIR}/bin/authserver" ] && echo "    authserver: found" || echo "    authserver: missing"
        [ -f "${INSTALL_DIR}/bin/worldserver" ] && echo "    worldserver: found" || echo "    worldserver: missing"
    else
        echo "  Install directory: ${INSTALL_DIR} (missing)"
    fi

    echo ""
    echo "PostgreSQL:"
    if [ -d "${BUILD_DIR_POSTGRES}" ]; then
        echo "  Build directory: ${BUILD_DIR_POSTGRES} (exists)"
    else
        echo "  Build directory: ${BUILD_DIR_POSTGRES} (missing)"
    fi
    if [ -d "${INSTALL_DIR_POSTGRES}" ]; then
        echo "  Install directory: ${INSTALL_DIR_POSTGRES} (exists)"
        [ -f "${INSTALL_DIR_POSTGRES}/bin/authserver" ] && echo "    authserver: found" || echo "    authserver: missing"
        [ -f "${INSTALL_DIR_POSTGRES}/bin/worldserver" ] && echo "    worldserver: found" || echo "    worldserver: missing"
    else
        echo "  Install directory: ${INSTALL_DIR_POSTGRES} (missing)"
    fi

    echo ""
    echo "=== Database Connectivity ==="
    echo "MySQL:"
    for container in "${MYSQL_CONTAINERS[@]}"; do
        echo -n "  ${container}: "
        if podman container exists "${container}" 2>/dev/null; then
            status=$(podman inspect "${container}" --format='{{.State.Status}}' 2>/dev/null || echo "unknown")
            if [ "${status}" = "running" ]; then
                if podman exec "${container}" mysqladmin -u "${DB_USER}" -p"${DB_PASSWORD}" ping &>/dev/null; then
                    echo "running, connected"
                else
                    echo "running, connection failed"
                fi
            else
                echo "${status}"
            fi
        else
            echo "does not exist"
        fi
    done

    echo ""
    echo "PostgreSQL:"
    for container in "${POSTGRES_CONTAINERS[@]}"; do
        echo -n "  ${container}: "
        if podman container exists "${container}" 2>/dev/null; then
            status=$(podman inspect "${container}" --format='{{.State.Status}}' 2>/dev/null || echo "unknown")
            if [ "${status}" = "running" ]; then
                if podman exec "${container}" pg_isready -U "${DB_USER}" &>/dev/null; then
                    echo "running, connected"
                else
                    echo "running, connection failed"
                fi
            else
                echo "${status}"
            fi
        else
            echo "does not exist"
        fi
    done
}

function cleanup_all() {
    echo "Performing full cleanup..."
    cleanup_containers
    rm -rf "${BUILD_DIR}" "${INSTALL_DIR}" "${BUILD_DIR_POSTGRES}" "${INSTALL_DIR_POSTGRES}"
    echo "Full cleanup completed"
}

# Main command processing
case "${1:-}" in
    setup-containers)
        setup_containers
        ;;
    setup-mysql)
        setup_mysql
        ;;
    setup-postgres)
        setup_postgres
        ;;
    start-containers)
        start_containers
        ;;
    stop-containers)
        stop_containers
        ;;
    cleanup-containers)
        cleanup_containers
        ;;
    reset-databases)
        reset_databases
        ;;
    build)
        build
        ;;
    build-postgres)
        build_postgres
        ;;
    build-all)
        build_all
        ;;
    configure)
        configure
        ;;
    configure-postgres)
        configure_postgres
        ;;
    test)
        test_server
        ;;
    test-postgres)
        test_postgres
        ;;
    test-both)
        test_both
        ;;
    convert-sql)
        convert_sql
        ;;
    status)
        show_status
        ;;
    cleanup-all)
        cleanup_all
        ;;
    *)
        show_usage
        exit 1
        ;;
esac
