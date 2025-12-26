#!/bin/bash

# SPDX-License-Identifier: GPL-2.0-or-later
#
# Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors

# Build TrinityCore for development with selectable database backend

set -e

# Default settings
BUILD_TYPE="${BUILD_TYPE:-Debug}"
JOBS="${JOBS:-$(nproc)}"
BUILD_MYSQL=0
BUILD_POSTGRESQL=0

usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Build TrinityCore with MySQL or PostgreSQL backend"
    echo ""
    echo "Options:"
    echo "  --mysql       Build with MySQL backend (default if no option specified)"
    echo "  --postgresql  Build with PostgreSQL backend"
    echo "  --both        Build with both backends"
    echo "  -j, --jobs N  Number of parallel jobs (default: $(nproc))"
    echo "  -j all        Use all available CPU cores"
    echo "  --help        Show this help message"
    echo ""
    echo "Environment variables:"
    echo "  BUILD_TYPE    CMake build type (default: Debug)"
    echo "  JOBS          Parallel build jobs (default: $(nproc))"
    exit 0
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --mysql)
            BUILD_MYSQL=1
            shift
            ;;
        --postgresql)
            BUILD_POSTGRESQL=1
            shift
            ;;
        --both)
            BUILD_MYSQL=1
            BUILD_POSTGRESQL=1
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

# Default to MySQL if no backend specified
if [[ $BUILD_MYSQL -eq 0 && $BUILD_POSTGRESQL -eq 0 ]]; then
    BUILD_MYSQL=1
fi

build_backend() {
    local BACKEND=$1
    local WITH_POSTGRESQL=$2
    local BUILD_DIR="build-cata-${BACKEND}"
    local INSTALL_DIR="$(pwd)/install-cata-${BACKEND}"

    echo "====================================="
    echo "Building TrinityCore (${BACKEND})"
    echo "====================================="
    echo "Build directory: ${BUILD_DIR}"
    echo "Install directory: ${INSTALL_DIR}"
    echo "Build type: ${BUILD_TYPE}"
    echo "Parallel jobs: ${JOBS}"
    echo "====================================="

    # Create build directory
    mkdir -p "${BUILD_DIR}"

    # Configure
    cmake -S . -B "${BUILD_DIR}" \
        -DCMAKE_BUILD_TYPE="${BUILD_TYPE}" \
        -DCMAKE_INSTALL_PREFIX="${INSTALL_DIR}" \
        -DWITH_POSTGRESQL="${WITH_POSTGRESQL}" \
        -DWITH_WARNINGS=ON \
        -DWITH_COREDEBUG=ON \
        -DBUILD_TESTING=ON \
        -DUSE_COREPCH=ON \
        -DUSE_SCRIPTPCH=ON \
        -DSERVERS=ON \
        -DTOOLS=ON \
        -DSCRIPTS=static

    # Build
    cmake --build "${BUILD_DIR}" -j "${JOBS}"

    # Install
    cmake --install "${BUILD_DIR}"

    echo ""
    echo "====================================="
    echo "Build completed successfully! (${BACKEND})"
    echo "====================================="
    echo "Install location: ${INSTALL_DIR}"
    echo ""
}

# Build requested backends
if [[ $BUILD_MYSQL -eq 1 ]]; then
    build_backend "mysql" "OFF"
fi

if [[ $BUILD_POSTGRESQL -eq 1 ]]; then
    build_backend "postgresql" "ON"
fi

echo "To run:"
echo "  cd install-cata-<backend>"
echo "  ./bin/bnetserver -c etc/bnetserver.conf"
echo "  ./bin/worldserver -c etc/worldserver.conf"
