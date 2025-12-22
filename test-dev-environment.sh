#!/bin/bash

# SPDX-License-Identifier: GPL-2.0-or-later
#
# Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors

# TrinityCore Development Test Environment Manager (3.3.5 WotLK)
# This script manages podman containers and test installations for MySQL backend testing

set -e

# Branch-specific defaults to avoid collisions when working on multiple branches
# 3.3.5: containers trinity-335-mysql-*, ports 335xx, dirs *-335
CONTAINER_PREFIX="${CONTAINER_PREFIX:-trinity-335}"
MYSQL_AUTH_CONTAINER="${CONTAINER_PREFIX}-mysql-auth"
MYSQL_CHAR_CONTAINER="${CONTAINER_PREFIX}-mysql-characters"
MYSQL_WORLD_CONTAINER="${CONTAINER_PREFIX}-mysql-world"
MYSQL_VERSION="${MYSQL_VERSION:-8}"
MYSQL_PASSWORD="${MYSQL_PASSWORD:-trinity}"

# Ports: auth=33506, characters=33507, world=33508
MYSQL_AUTH_PORT="${MYSQL_AUTH_PORT:-33506}"
MYSQL_CHAR_PORT="${MYSQL_CHAR_PORT:-33507}"
MYSQL_WORLD_PORT="${MYSQL_WORLD_PORT:-33508}"

BUILD_DIR="${BUILD_DIR:-build-335}"
INSTALL_DIR="${INSTALL_DIR:-$(pwd)/install-335}"

function show_usage() {
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  setup-containers     Create and start MySQL database containers"
    echo "  start-containers     Start existing containers"
    echo "  stop-containers      Stop running containers"
    echo "  cleanup-containers   Stop and remove all database containers"
    echo "  reset-databases      Drop and recreate all databases (empty state)"
    echo "  build                Build TrinityCore for development"
    echo "  configure            Create configuration files from templates"
    echo "  test                 Test MySQL backend (start authserver briefly)"
    echo "  status               Show container and build status"
    echo "  cleanup-all          Full cleanup (containers + builds)"
    echo ""
    echo "Environment variables:"
    echo "  CONTAINER_PREFIX     Container name prefix (default: trinity-335)"
    echo "  MYSQL_VERSION        MySQL image version (default: 8)"
    echo "  MYSQL_PASSWORD       MySQL password (default: trinity)"
    echo "  BUILD_DIR            Build directory (default: build-335)"
    echo "  INSTALL_DIR          Install directory (default: ./install-335)"
    echo ""
    echo "Databases (3.3.5 WotLK):"
    echo "  auth       - Login/authentication database (port 33506)"
    echo "  characters - Character data database (port 33507)"
    echo "  world      - World content database (port 33508)"
    echo ""
}

function setup_containers() {
    echo "Setting up MySQL database containers..."

    # MySQL container for auth database
    if ! podman container exists "${MYSQL_AUTH_CONTAINER}"; then
        echo "Creating MySQL container for auth database (port ${MYSQL_AUTH_PORT})..."
        podman run -d --name "${MYSQL_AUTH_CONTAINER}" \
            -e MYSQL_ROOT_PASSWORD="${MYSQL_PASSWORD}" \
            -e MYSQL_USER=trinity \
            -e MYSQL_PASSWORD="${MYSQL_PASSWORD}" \
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
            -e MYSQL_ROOT_PASSWORD="${MYSQL_PASSWORD}" \
            -e MYSQL_USER=trinity \
            -e MYSQL_PASSWORD="${MYSQL_PASSWORD}" \
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
            -e MYSQL_ROOT_PASSWORD="${MYSQL_PASSWORD}" \
            -e MYSQL_USER=trinity \
            -e MYSQL_PASSWORD="${MYSQL_PASSWORD}" \
            -e MYSQL_DATABASE=trinity_world \
            -p "${MYSQL_WORLD_PORT}:3306" \
            "mysql:${MYSQL_VERSION}"
    else
        echo "Container ${MYSQL_WORLD_CONTAINER} already exists"
        podman start "${MYSQL_WORLD_CONTAINER}" 2>/dev/null || true
    fi

    echo "Waiting for containers to be ready..."
    sleep 10

    echo ""
    echo "MySQL containers ready:"
    echo "  Auth:       localhost:${MYSQL_AUTH_PORT} (database: trinity_auth)"
    echo "  Characters: localhost:${MYSQL_CHAR_PORT} (database: trinity_characters)"
    echo "  World:      localhost:${MYSQL_WORLD_PORT} (database: trinity_world)"
    echo "  User:       trinity"
    echo "  Password:   ${MYSQL_PASSWORD}"
}

function start_containers() {
    echo "Starting database containers..."
    for container in "${MYSQL_AUTH_CONTAINER}" "${MYSQL_CHAR_CONTAINER}" "${MYSQL_WORLD_CONTAINER}"; do
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
    for container in "${MYSQL_AUTH_CONTAINER}" "${MYSQL_CHAR_CONTAINER}" "${MYSQL_WORLD_CONTAINER}"; do
        if podman container exists "${container}"; then
            echo "Stopping ${container}..."
            podman stop "${container}" || true
        fi
    done
}

function cleanup_containers() {
    echo "Cleaning up database containers..."
    for container in "${MYSQL_AUTH_CONTAINER}" "${MYSQL_CHAR_CONTAINER}" "${MYSQL_WORLD_CONTAINER}"; do
        if podman container exists "${container}"; then
            echo "Stopping and removing ${container}..."
            podman stop "${container}" 2>/dev/null || true
            podman rm "${container}" 2>/dev/null || true
        fi
    done
    echo "Containers removed"
}

function reset_databases() {
    echo "Resetting all databases to empty state..."

    # Reset auth database
    if podman container exists "${MYSQL_AUTH_CONTAINER}"; then
        echo "Resetting auth database..."
        podman exec "${MYSQL_AUTH_CONTAINER}" mysql -u trinity -p"${MYSQL_PASSWORD}" -e "
            DROP DATABASE IF EXISTS trinity_auth;
            CREATE DATABASE trinity_auth;" 2>/dev/null || echo "Warning: Could not reset auth database"
    fi

    # Reset characters database
    if podman container exists "${MYSQL_CHAR_CONTAINER}"; then
        echo "Resetting characters database..."
        podman exec "${MYSQL_CHAR_CONTAINER}" mysql -u trinity -p"${MYSQL_PASSWORD}" -e "
            DROP DATABASE IF EXISTS trinity_characters;
            CREATE DATABASE trinity_characters;" 2>/dev/null || echo "Warning: Could not reset characters database"
    fi

    # Reset world database
    if podman container exists "${MYSQL_WORLD_CONTAINER}"; then
        echo "Resetting world database..."
        podman exec "${MYSQL_WORLD_CONTAINER}" mysql -u trinity -p"${MYSQL_PASSWORD}" -e "
            DROP DATABASE IF EXISTS trinity_world;
            CREATE DATABASE trinity_world;" 2>/dev/null || echo "Warning: Could not reset world database"
    fi

    echo "Databases reset complete"
}

function build() {
    echo "Building TrinityCore..."

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

function configure() {
    echo "Creating configuration files..."

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
    sed -i "s|^LoginDatabaseInfo = .*|LoginDatabaseInfo = \"127.0.0.1;${MYSQL_AUTH_PORT};trinity;${MYSQL_PASSWORD};trinity_auth\"|" \
        "${INSTALL_DIR}/etc/authserver.conf"
    sed -i 's|^Updates.EnableDatabases = .*|Updates.EnableDatabases = 1|' \
        "${INSTALL_DIR}/etc/authserver.conf"
    sed -i 's|^MySQLExecutable = .*|MySQLExecutable = "/usr/bin/mysql"|' \
        "${INSTALL_DIR}/etc/authserver.conf"

    # Update worldserver configuration
    sed -i "s|^LoginDatabaseInfo = .*|LoginDatabaseInfo = \"127.0.0.1;${MYSQL_AUTH_PORT};trinity;${MYSQL_PASSWORD};trinity_auth\"|" \
        "${INSTALL_DIR}/etc/worldserver.conf"
    sed -i "s|^CharacterDatabaseInfo = .*|CharacterDatabaseInfo = \"127.0.0.1;${MYSQL_CHAR_PORT};trinity;${MYSQL_PASSWORD};trinity_characters\"|" \
        "${INSTALL_DIR}/etc/worldserver.conf"
    sed -i "s|^WorldDatabaseInfo = .*|WorldDatabaseInfo = \"127.0.0.1;${MYSQL_WORLD_PORT};trinity;${MYSQL_PASSWORD};trinity_world\"|" \
        "${INSTALL_DIR}/etc/worldserver.conf"
    # Enable auto-updates for characters (2) + world (4) = 6, but not auth (handled by authserver)
    sed -i 's|^Updates.EnableDatabases = .*|Updates.EnableDatabases = 6|' \
        "${INSTALL_DIR}/etc/worldserver.conf"
    sed -i 's|^MySQLExecutable = .*|MySQLExecutable = "/usr/bin/mysql"|' \
        "${INSTALL_DIR}/etc/worldserver.conf"

    echo "Configuration files created in ${INSTALL_DIR}/etc/"
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
        echo "authserver started successfully"
        kill "${AUTH_PID}" 2>/dev/null || true
        wait "${AUTH_PID}" 2>/dev/null || true
        cd - >/dev/null
        return 0
    else
        echo "authserver failed to start"
        cd - >/dev/null
        return 1
    fi
}

function show_status() {
    echo "=== Container Status ==="
    if command -v podman &>/dev/null; then
        podman ps -a --filter "name=${CONTAINER_PREFIX}-mysql" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    else
        echo "podman not found"
    fi

    echo ""
    echo "=== Build Status ==="
    if [ -d "${BUILD_DIR}" ]; then
        echo "Build directory: ${BUILD_DIR} (exists)"
    else
        echo "Build directory: ${BUILD_DIR} (missing)"
    fi

    if [ -d "${INSTALL_DIR}" ]; then
        echo "Install directory: ${INSTALL_DIR} (exists)"
        [ -f "${INSTALL_DIR}/bin/authserver" ] && echo "  authserver: found" || echo "  authserver: missing"
        [ -f "${INSTALL_DIR}/bin/worldserver" ] && echo "  worldserver: found" || echo "  worldserver: missing"
    else
        echo "Install directory: ${INSTALL_DIR} (missing)"
    fi

    echo ""
    echo "=== Database Connectivity ==="
    for container in "${MYSQL_AUTH_CONTAINER}" "${MYSQL_CHAR_CONTAINER}" "${MYSQL_WORLD_CONTAINER}"; do
        echo -n "${container}: "
        if podman container exists "${container}" 2>/dev/null; then
            status=$(podman inspect "${container}" --format='{{.State.Status}}' 2>/dev/null || echo "unknown")
            if [ "${status}" = "running" ]; then
                if podman exec "${container}" mysqladmin -u trinity -p"${MYSQL_PASSWORD}" ping &>/dev/null; then
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
    rm -rf "${BUILD_DIR}" "${INSTALL_DIR}"
    echo "Full cleanup completed"
}

# Main command processing
case "${1:-}" in
    setup-containers)
        setup_containers
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
    configure)
        configure
        ;;
    test)
        test_server
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
