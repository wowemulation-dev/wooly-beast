#!/bin/bash

# SPDX-License-Identifier: GPL-2.0-or-later
#
# Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors

# Build TrinityCore for development with configurable database backend

set -e

# Configuration
BUILD_TYPE="${BUILD_TYPE:-Debug}"
JOBS="${JOBS:-1}"  # Default to 1 for easier error reading
BRANCH_SUFFIX="335"

# Database backend selection
# Options: mysql, postgresql, both
BACKEND="${BACKEND:-mysql}"

usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --mysql       Build with MySQL backend only (default)"
    echo "  --postgresql  Build with PostgreSQL backend only"
    echo "  --both        Build with both MySQL and PostgreSQL backends"
    echo "  -j, --jobs N  Number of parallel jobs (default: 1)"
    echo "  -j all        Use all available CPU cores"
    echo "  --help        Show this help message"
    echo ""
    echo "Environment variables:"
    echo "  BUILD_TYPE    CMake build type (default: Debug)"
    echo "  JOBS          Number of parallel jobs (default: 1)"
    echo "  BACKEND       Database backend: mysql, postgresql, both (default: mysql)"
    exit 0
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --mysql)
            BACKEND="mysql"
            shift
            ;;
        --postgresql)
            BACKEND="postgresql"
            shift
            ;;
        --both)
            BACKEND="both"
            shift
            ;;
        -j|--jobs)
            if [[ "$2" == "all" ]]; then
                JOBS="$(nproc)"
            elif [[ "$2" =~ ^[0-9]+$ ]]; then
                JOBS="$2"
            else
                echo "Error: -j requires a number or 'all'"
                exit 1
            fi
            shift 2
            ;;
        --help|-h)
            usage
            ;;
        *)
            echo "Unknown option: $1"
            usage
            ;;
    esac
done

build_backend() {
    local backend=$1
    local with_postgresql=0
    local backend_name

    if [[ "$backend" == "postgresql" ]]; then
        with_postgresql=1
        backend_name="PostgreSQL"
    else
        backend_name="MySQL"
    fi

    local build_dir="build-${BRANCH_SUFFIX}-${backend}"
    local install_dir="$(pwd)/install-${BRANCH_SUFFIX}-${backend}"

    echo "====================================="
    echo "Building TrinityCore (${backend_name})"
    echo "====================================="
    echo "Build directory: ${build_dir}"
    echo "Install directory: ${install_dir}"
    echo "Build type: ${BUILD_TYPE}"
    echo "Parallel jobs: ${JOBS}"
    echo "====================================="

    # Create build directory
    mkdir -p "${build_dir}"

    # Configure
    cmake -S . -B "${build_dir}" \
        -DCMAKE_BUILD_TYPE="${BUILD_TYPE}" \
        -DCMAKE_INSTALL_PREFIX="${install_dir}" \
        -DWITH_WARNINGS=ON \
        -DWITH_COREDEBUG=ON \
        -DBUILD_TESTING=ON \
        -DUSE_COREPCH=ON \
        -DUSE_SCRIPTPCH=ON \
        -DSERVERS=ON \
        -DTOOLS=ON \
        -DSCRIPTS=static \
        -DWITH_POSTGRESQL="${with_postgresql}"

    # Build
    cmake --build "${build_dir}" -j "${JOBS}"

    # Install
    cmake --install "${build_dir}"

    echo ""
    echo "====================================="
    echo "${backend_name} build completed!"
    echo "====================================="
    echo "Install location: ${install_dir}"
    echo ""
}

# Build requested backends
case $BACKEND in
    mysql)
        build_backend mysql
        ;;
    postgresql)
        build_backend postgresql
        ;;
    both)
        build_backend mysql
        echo ""
        build_backend postgresql
        ;;
esac

echo "====================================="
echo "All builds completed successfully!"
echo "====================================="
echo ""
echo "To run (MySQL):"
echo "  cd install-${BRANCH_SUFFIX}-mysql"
echo "  ./bin/authserver -c etc/authserver.conf"
echo "  ./bin/worldserver -c etc/worldserver.conf"
if [[ "$BACKEND" == "both" || "$BACKEND" == "postgresql" ]]; then
    echo ""
    echo "To run (PostgreSQL):"
    echo "  cd install-${BRANCH_SUFFIX}-postgresql"
    echo "  ./bin/authserver -c etc/authserver.conf"
    echo "  ./bin/worldserver -c etc/worldserver.conf"
fi
