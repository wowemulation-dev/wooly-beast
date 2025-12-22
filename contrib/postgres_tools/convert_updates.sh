#!/bin/bash

# SPDX-License-Identifier: GPL-2.0-or-later
#
# Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors

# TrinityCore MySQL to PostgreSQL Update Converter
# Converts update files from sql/updates to PostgreSQL format

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
CONVERTER="$SCRIPT_DIR/mysql_to_postgres_converter.py"

# Branch version (cata_classic for Cataclysm, 3.3.5 for WotLK)
BRANCH_VERSION="${BRANCH_VERSION:-cata_classic}"

# Source is the branch version directory, target is postgresql subdirectory
SOURCE_DIR="${1:-$SCRIPT_DIR/../../sql/updates}"
TARGET_BASE="${2:-$SOURCE_DIR}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "TrinityCore MySQL to PostgreSQL Update Converter"
echo "================================================"
echo "Branch version: $BRANCH_VERSION"
echo

# Check if converter exists
if [ ! -f "$CONVERTER" ]; then
    echo -e "${RED}Error: Converter script not found at $CONVERTER${NC}"
    exit 1
fi

# Check if source directory exists
if [ ! -d "$SOURCE_DIR" ]; then
    echo -e "${RED}Error: Source directory not found at $SOURCE_DIR${NC}"
    exit 1
fi

# Process each database type (including hotfixes for Cata Classic)
for db_type in auth characters world hotfixes; do
    DB_SOURCE="$SOURCE_DIR/$db_type/$BRANCH_VERSION"
    DB_TARGET="$TARGET_BASE/$db_type/$BRANCH_VERSION/postgresql"

    if [ ! -d "$DB_SOURCE" ]; then
        echo -e "${YELLOW}Skipping $db_type: Source directory not found${NC}"
        continue
    fi

    # Create target directory
    mkdir -p "$DB_TARGET"

    echo "Processing $db_type updates..."
    echo "  Source: $DB_SOURCE"
    echo "  Target: $DB_TARGET"

    # Convert each SQL file (exclude postgresql subdirectory)
    for file in "$DB_SOURCE"/*.sql; do
        if [ ! -f "$file" ]; then
            continue
        fi

        filename=$(basename "$file")
        TARGET_FILE="$DB_TARGET/$filename"

        # Skip if already converted and newer than source
        if [ -f "$TARGET_FILE" ] && [ "$TARGET_FILE" -nt "$file" ]; then
            echo -e "  ${YELLOW}Skipping${NC} $filename (already converted)"
            continue
        fi

        # Convert the file
        echo -n "  Converting $filename... "
        if python3 "$CONVERTER" "$file" "$TARGET_FILE" 2>/dev/null; then
            echo -e "${GREEN}OK${NC}"
        else
            echo -e "${RED}FAILED${NC}"
            # Try to get error details
            python3 "$CONVERTER" "$file" "$TARGET_FILE" 2>&1 | tail -3
        fi
    done

    echo
done

echo "Conversion complete!"
echo "==================="
echo
echo "PostgreSQL update files are in: $TARGET_BASE/*/\$BRANCH_VERSION/postgresql/"
echo
echo "To apply updates to PostgreSQL:"
echo "1. Navigate to the PostgreSQL updates directory"
echo "2. Apply updates in order using psql or through TrinityCore's auto-updater"
