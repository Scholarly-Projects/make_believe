#!/usr/bin/env python3
"""
renumber_citations.py
---------------------
"""

import csv
import os
import re
import sys

ESSAY_DIR = "_essay"
CITATION_CSV = os.path.join("_data", "citation.csv")

# Matches a bare ^ or ^N (caret followed by zero or more digits)
# Requires the caret to not be preceded by another caret (avoids ^^ edge cases)
CITATION_PATTERN = re.compile(r'(?<!\^)\^\d*')


# ---------------------------------------------------------------------------
# CSV: renumber rows and return the total count
# ---------------------------------------------------------------------------

def renumber_csv():
    """
    Renumber all citation IDs in citation.csv to citation_001, citation_002, etc.
    Returns the total number of rows (i.e. the expected number of markers).
    """
    if not os.path.isfile(CITATION_CSV):
        print(f"Error: '{CITATION_CSV}' not found.")
        print("Run this script from your project root.")
        sys.exit(1)

    with open(CITATION_CSV, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    for i, row in enumerate(rows, start=1):
        row["id"] = f"citation_{i:03d}"

    with open(CITATION_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"  Updated CSV:   {CITATION_CSV} ({len(rows)} citations)")
    return len(rows)


# ---------------------------------------------------------------------------
# Essays: renumber all markers across files in chapter order
# ---------------------------------------------------------------------------

def parse_order(filepath):
    """Extract the 'order' value from YAML front matter."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    match = re.search(r"^order:\s*(\d+)", content, re.MULTILINE)
    return int(match.group(1)) if match else 9999


def get_essay_files():
    """Return essay .md files sorted by their front matter 'order' field."""
    files = [
        os.path.join(ESSAY_DIR, f)
        for f in os.listdir(ESSAY_DIR)
        if f.endswith(".md")
    ]
    return sorted(files, key=parse_order)


def renumber_essays(files, expected_total):
    """
    Renumber all ^ and ^N markers across essay files sequentially from 1,
    in chapter order. Warns if the count doesn't match the CSV row total.
    """
    # First pass: count total markers across all files
    total_found = sum(
        len(CITATION_PATTERN.findall(open(f, "r", encoding="utf-8").read()))
        for f in files
    )

    if total_found != expected_total:
        print(
            f"\n  Warning: {total_found} citation marker(s) found in essays "
            f"but {expected_total} row(s) in citation.csv — check for mismatches "
            f"before pushing.\n"
        )

    # Second pass: renumber sequentially across all files
    counter = 1
    for filepath in files:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        def replacer(match):
            nonlocal counter
            result = f"^{counter}"
            counter += 1
            return result

        new_content = CITATION_PATTERN.sub(replacer, content)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)

        print(f"  Updated essay: {filepath}")

    return counter - 1


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if not os.path.isdir(ESSAY_DIR):
        print(f"Error: '{ESSAY_DIR}' directory not found.")
        print("Run this script from your project root (where _essay/ lives).")
        sys.exit(1)

    files = get_essay_files()
    if not files:
        print(f"No .md files found in '{ESSAY_DIR}'.")
        sys.exit(0)

    print("\nStep 1: Renumbering citation.csv...")
    expected_total = renumber_csv()

    print("\nStep 2: Renumbering citation markers in essays...")
    actual_total = renumber_essays(files, expected_total)

    print(f"\nDone. {actual_total} citation(s) renumbered across {len(files)} essay file(s).")


if __name__ == "__main__":
    main()