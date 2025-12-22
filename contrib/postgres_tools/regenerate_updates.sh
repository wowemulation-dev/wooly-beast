#!/bin/bash

# SPDX-License-Identifier: GPL-2.0-or-later
#
# Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors

# Script to regenerate all PostgreSQL update files from MySQL versions

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_PATH="$SCRIPT_DIR/../../sql/updates"

# Branch version (3.3.5 for WotLK, cata_classic for Cataclysm)
BRANCH_VERSION="${BRANCH_VERSION:-3.3.5}"

# Ensure uv dependencies are installed
cd "$SCRIPT_DIR"
if [ ! -d ".venv" ]; then
    echo "Installing converter dependencies..."
    uv sync
fi

echo "Regenerating PostgreSQL updates for branch: $BRANCH_VERSION"

# Function to convert update files for a specific database
convert_updates() {
    local db_name=$1
    local mysql_dir="$BASE_PATH/$db_name/$BRANCH_VERSION"
    local postgres_dir="$BASE_PATH/$db_name/$BRANCH_VERSION/postgresql"

    if [ ! -d "$mysql_dir" ]; then
        echo "MySQL directory not found: $mysql_dir"
        return 1
    fi

    echo "Processing $db_name updates..."

    # Create PostgreSQL directory if it doesn't exist
    mkdir -p "$postgres_dir"

    # Convert each MySQL file (exclude postgresql subdirectory)
    for mysql_file in "$mysql_dir"/*.sql; do
        if [ -f "$mysql_file" ]; then
            base_name=$(basename "$mysql_file")
            postgres_file="$postgres_dir/$base_name"

            echo "  Converting $base_name..."
            uv run --directory "$SCRIPT_DIR" mysql-to-postgres "$mysql_file" "$postgres_file"
        fi
    done
}

# Convert updates for each database
for db in auth characters world; do
    convert_updates "$db"
done

echo "Conversion complete!"
