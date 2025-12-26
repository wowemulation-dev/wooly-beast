#!/usr/bin/env python3
"""
Diagnostic script to identify data loss during MySQL to PostgreSQL conversion.

Compares INSERT statement counts and row counts between original MySQL dump
and converted PostgreSQL dump.
"""

import re
import sys
from pathlib import Path
from collections import defaultdict


def count_insert_rows(filepath: Path) -> dict[str, int]:
    """Count INSERT rows per table in a SQL dump file."""
    table_counts = defaultdict(int)
    current_table = None

    # Pattern for INSERT INTO `table` or INSERT INTO table
    insert_pattern = re.compile(r"INSERT\s+INTO\s+[`\"]?(\w+)[`\"]?", re.IGNORECASE)

    # Pattern to count value tuples in VALUES clause
    # This counts opening parens that start a value tuple
    values_pattern = re.compile(r"\((?:[^()]*|\([^()]*\))*\)")

    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        for line_num, line in enumerate(f, 1):
            # Check for INSERT statement
            match = insert_pattern.search(line)
            if match:
                current_table = match.group(1).lower()

                # Count value tuples in this line
                # Find VALUES clause
                values_pos = line.upper().find('VALUES')
                if values_pos != -1:
                    values_part = line[values_pos + 6:]
                    # Count top-level parentheses groups
                    depth = 0
                    count = 0
                    for char in values_part:
                        if char == '(':
                            if depth == 0:
                                count += 1
                            depth += 1
                        elif char == ')':
                            depth -= 1

                    table_counts[current_table] += count

            if line_num % 100000 == 0:
                print(f"  Processed {line_num:,} lines...", file=sys.stderr)

    return dict(table_counts)


def compare_dumps(mysql_path: Path, pg_path: Path) -> dict:
    """Compare row counts between MySQL and PostgreSQL dumps."""
    print(f"Analyzing MySQL dump: {mysql_path}", file=sys.stderr)
    mysql_counts = count_insert_rows(mysql_path)

    print(f"Analyzing PostgreSQL dump: {pg_path}", file=sys.stderr)
    pg_counts = count_insert_rows(pg_path)

    # Combine all tables
    all_tables = set(mysql_counts.keys()) | set(pg_counts.keys())

    results = {}
    for table in sorted(all_tables):
        mysql_count = mysql_counts.get(table, 0)
        pg_count = pg_counts.get(table, 0)
        diff = mysql_count - pg_count

        results[table] = {
            'mysql': mysql_count,
            'postgresql': pg_count,
            'difference': diff,
            'pct_missing': (diff / mysql_count * 100) if mysql_count > 0 else 0
        }

    return results


def print_report(results: dict):
    """Print comparison report."""
    print("\n" + "=" * 80)
    print("MySQL to PostgreSQL Conversion Diagnostic Report")
    print("=" * 80)

    # Summary stats
    total_mysql = sum(r['mysql'] for r in results.values())
    total_pg = sum(r['postgresql'] for r in results.values())
    total_missing = total_mysql - total_pg

    print(f"\nTotal Rows: MySQL={total_mysql:,} PostgreSQL={total_pg:,} Missing={total_missing:,}")
    print(f"Overall Loss: {(total_missing/total_mysql*100):.2f}%\n")

    # Tables with data loss (sorted by missing count)
    print("-" * 80)
    print(f"{'Table':<40} {'MySQL':>10} {'PG':>10} {'Missing':>10} {'% Loss':>8}")
    print("-" * 80)

    # Sort by difference descending
    sorted_results = sorted(results.items(), key=lambda x: x[1]['difference'], reverse=True)

    for table, counts in sorted_results:
        if counts['difference'] != 0:
            print(f"{table:<40} {counts['mysql']:>10,} {counts['postgresql']:>10,} "
                  f"{counts['difference']:>10,} {counts['pct_missing']:>7.1f}%")

    # Tables with complete data
    complete = [(t, c) for t, c in sorted_results if c['difference'] == 0 and c['mysql'] > 0]
    if complete:
        print(f"\n{len(complete)} tables with complete data (no loss)")

    # Tables only in one dump
    mysql_only = [t for t, c in results.items() if c['postgresql'] == 0 and c['mysql'] > 0]
    pg_only = [t for t, c in results.items() if c['mysql'] == 0 and c['postgresql'] > 0]

    if mysql_only:
        print(f"\nTables only in MySQL ({len(mysql_only)}):")
        for t in mysql_only[:10]:
            print(f"  - {t} ({results[t]['mysql']:,} rows)")
        if len(mysql_only) > 10:
            print(f"  ... and {len(mysql_only) - 10} more")

    if pg_only:
        print(f"\nTables only in PostgreSQL ({len(pg_only)}):")
        for t in pg_only[:10]:
            print(f"  - {t} ({results[t]['postgresql']:,} rows)")


def find_insert_line(filepath: Path, table: str, limit: int = 5):
    """Find INSERT statements for a specific table."""
    insert_pattern = re.compile(
        rf"INSERT\s+INTO\s+[`\"]?{re.escape(table)}[`\"]?",
        re.IGNORECASE
    )

    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        count = 0
        for line_num, line in enumerate(f, 1):
            if insert_pattern.search(line):
                print(f"Line {line_num}: {line[:200]}...")
                count += 1
                if count >= limit:
                    break


def main():
    if len(sys.argv) < 3:
        print("Usage: diagnose_conversion.py <mysql_dump.sql> <postgresql_dump.sql> [table]")
        print("\nExamples:")
        print("  diagnose_conversion.py TDB_mysql.sql TDB_pg.sql")
        print("  diagnose_conversion.py TDB_mysql.sql TDB_pg.sql item_template")
        sys.exit(1)

    mysql_path = Path(sys.argv[1])
    pg_path = Path(sys.argv[2])

    if not mysql_path.exists():
        print(f"Error: MySQL dump not found: {mysql_path}")
        sys.exit(1)

    if not pg_path.exists():
        print(f"Error: PostgreSQL dump not found: {pg_path}")
        sys.exit(1)

    # If specific table requested, show INSERT lines
    if len(sys.argv) > 3:
        table = sys.argv[3]
        print(f"\n=== INSERT statements for '{table}' in MySQL dump ===")
        find_insert_line(mysql_path, table)
        print(f"\n=== INSERT statements for '{table}' in PostgreSQL dump ===")
        find_insert_line(pg_path, table)
        return

    # Full comparison
    results = compare_dumps(mysql_path, pg_path)
    print_report(results)


if __name__ == '__main__':
    main()
