#!/bin/bash

# SPDX-License-Identifier: GPL-2.0-or-later
#
# Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors

# Script to convert all MySQL updates to PostgreSQL format

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SQL_DIR="$SCRIPT_DIR/../../sql/updates"

# Ensure uv dependencies are installed
cd "$SCRIPT_DIR"
if [ ! -d ".venv" ]; then
    echo "Installing converter dependencies..."
    uv sync
fi

# Branch version (cata_classic for Cataclysm, 3.3.5 for WotLK)
BRANCH_VERSION="${BRANCH_VERSION:-cata_classic}"

echo "Converting MySQL updates to PostgreSQL format..."
echo "Branch version: $BRANCH_VERSION"

# Function to convert updates for a specific database
convert_database_updates() {
    local db_name=$1
    local mysql_dir="$SQL_DIR/$db_name/$BRANCH_VERSION"
    local pg_dir="$SQL_DIR/$db_name/$BRANCH_VERSION/postgresql"

    if [ ! -d "$mysql_dir" ]; then
        echo "Skipping $db_name: Directory not found at $mysql_dir"
        return
    fi

    echo "Converting $db_name updates..."

    # Create PostgreSQL directory if it doesn't exist
    mkdir -p "$pg_dir"

    # Convert each MySQL file (exclude postgresql subdirectory)
    for sql_file in "$mysql_dir"/*.sql; do
        if [ -f "$sql_file" ]; then
            filename=$(basename "$sql_file")
            echo "  Converting $filename..."
            uv run --directory "$SCRIPT_DIR" mysql-to-postgres "$sql_file" "$pg_dir/$filename" || {
                echo "  ERROR: Failed to convert $filename"
                # Continue with other files even if one fails
            }
        fi
    done
}

# Convert updates for each database (including hotfixes for Cata Classic)
convert_database_updates "auth"
convert_database_updates "characters"
convert_database_updates "world"
convert_database_updates "hotfixes"

echo "Conversion complete!"
echo ""
echo "Note: Please review the converted files for any issues."
echo "Some complex queries may need manual adjustment."
