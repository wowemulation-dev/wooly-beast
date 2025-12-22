#!/bin/bash

# SPDX-License-Identifier: GPL-2.0-or-later
#
# Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors

# Build TrinityCore for development with MySQL backend

set -e

# Branch-specific defaults to avoid collisions when working on multiple branches
BUILD_DIR="${BUILD_DIR:-build-335}"
INSTALL_DIR="${INSTALL_DIR:-$(pwd)/install-335}"
BUILD_TYPE="${BUILD_TYPE:-Debug}"
JOBS="${JOBS:-$(nproc)}"

echo "====================================="
echo "Building TrinityCore (Development)"
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
echo "Build completed successfully!"
echo "====================================="
echo "Install location: ${INSTALL_DIR}"
echo ""
echo "To run:"
echo "  cd ${INSTALL_DIR}"
echo "  ./bin/authserver -c etc/authserver.conf"
echo "  ./bin/worldserver -c etc/worldserver.conf"
