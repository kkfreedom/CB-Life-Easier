"""
SQL Parser Tool
===============
Parses MyBatis-style debug log lines and replaces ? placeholders with actual parameter values.

Usage:
    1. Run the script
    2. Paste the "Preparing:" log line
    3. Paste the "Parameters:" log line
    4. Get the fully resolved SQL query

Supports reading from clipboard and multi-line paste.
"""

import argparse
import re
import sys


def _strip_trailing_metadata(text: str) -> str:
    """Remove the trailing log metadata like '[c-http-26] [341] {Req#=...}' from a log line."""
    # Match trailing segments of [bracketed text] and {braced text} at end of line
    return re.sub(r'\s+\[\S+\](?:\s+\[\S+\])*(?:\s+\{[^}]*\})?\s*$', '', text).strip()


def extract_sql(preparing_line: str) -> str:
    """Extract the raw SQL from a 'Preparing:' log line."""
    match = re.search(r"Preparing:\s*(.+)$", preparing_line)
    if not match:
        raise ValueError("Could not find 'Preparing:' section in the input line.")
    return _strip_trailing_metadata(match.group(1))


def extract_parameters(parameters_line: str) -> list[tuple[str, str]]:
    """
    Extract parameters from a 'Parameters:' log line.
    Returns a list of (value, type) tuples.
    e.g. "3(Integer), hello(String)" -> [("3", "Integer"), ("hello", "String")]
    """
    match = re.search(r"Parameters:\s*(.+)$", parameters_line)
    if not match:
        return []

    params_str = _strip_trailing_metadata(match.group(1))
    if not params_str:
        return []

    params = []
    # Pattern: value(Type) — value can contain anything except the last (Type) part
    for token in re.split(r",\s*", params_str):
        token = token.strip()
        param_match = re.match(r"^(.+)\((\w+)\)$", token)
        if param_match:
            params.append((param_match.group(1).strip(), param_match.group(2).strip()))
        elif token.lower() == "null":
            params.append(("null", "Null"))
        else:
            params.append((token, "Unknown"))
    return params


# Types that should be quoted in the output SQL
_STRING_TYPES = {"String", "Varchar", "Char", "Text", "Date", "Timestamp", "Time", "Unknown"}
_NULL_TYPES = {"Null"}


def format_param(value: str, param_type: str) -> str:
    """Format a parameter value for SQL insertion based on its type."""
    if param_type in _NULL_TYPES or value.lower() == "null":
        return "NULL"
    if param_type in _STRING_TYPES:
        escaped = value.replace("'", "''")
        return f"'{escaped}'"
    # Numeric types (Integer, Long, BigDecimal, Float, Double, etc.)
    return value


def replace_placeholders(sql: str, params: list[tuple[str, str]]) -> str:
    """Replace each ? placeholder in the SQL with the corresponding parameter value."""
    result = []
    param_idx = 0
    i = 0
    in_single_quote = False
    in_double_quote = False

    while i < len(sql):
        char = sql[i]

        # Track string literals so we don't replace ? inside them
        if char == "'" and not in_double_quote:
            in_single_quote = not in_single_quote
            result.append(char)
        elif char == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
            result.append(char)
        elif char == "?" and not in_single_quote and not in_double_quote:
            if param_idx < len(params):
                value, ptype = params[param_idx]
                result.append(format_param(value, ptype))
                param_idx += 1
            else:
                result.append("?")  # Leave as-is if no more params
        else:
            result.append(char)
        i += 1

    return "".join(result)


def format_sql(sql: str) -> str:
    """Pretty-format the SQL with proper indentation for readability."""
    # Normalize whitespace
    sql = re.sub(r'\s+', ' ', sql).strip()

    INDENT = "    "

    # Major clause keywords — new line at current indent level
    major_kw = [
        "UNION ALL", "UNION DISTINCT",
        "INSERT INTO", "DELETE FROM",
        "LEFT OUTER JOIN", "RIGHT OUTER JOIN", "FULL OUTER JOIN",
        "INNER JOIN", "LEFT JOIN", "RIGHT JOIN", "FULL JOIN",
        "OUTER JOIN", "CROSS JOIN",
        "ORDER BY", "GROUP BY",
        "SELECT", "FROM", "WHERE", "HAVING", "JOIN",
        "LIMIT", "OFFSET", "VALUES", "UPDATE", "SET", "UNION",
    ]
    # Sub-clause keywords — new line, indented one level deeper
    sub_kw = ["AND", "OR", "ON"]

    major_set = {kw.upper() for kw in major_kw}
    sub_set = {kw.upper() for kw in sub_kw}

    # Build regex to split on keywords (longest match first)
    all_kw_sorted = sorted(major_kw + sub_kw, key=len, reverse=True)
    kw_pattern = "|".join(re.escape(kw) for kw in all_kw_sorted)
    pattern = rf'\b({kw_pattern})\b'

    tokens = re.split(pattern, sql, flags=re.IGNORECASE)

    lines = []
    indent_level = 0

    for token in tokens:
        stripped = token.strip()
        if not stripped:
            continue

        upper = stripped.upper()

        if upper in major_set:
            lines.append(f"{INDENT * indent_level}{upper}")
        elif upper in sub_set:
            lines.append(f"{INDENT * (indent_level + 1)}{upper}")
        else:
            # Non-keyword text — append to last line
            if lines:
                lines[-1] += f" {stripped}"
            else:
                lines.append(stripped)

            # Track parenthesis depth for subquery indentation
            in_str = False
            for ch in stripped:
                if ch == "'" :
                    in_str = not in_str
                elif not in_str:
                    if ch == '(':
                        indent_level += 1
                    elif ch == ')':
                        indent_level = max(0, indent_level - 1)

    return "\n".join(lines)


def parse_and_replace(preparing_line: str, parameters_line: str, pretty: bool = True) -> str:
    """
    Main entry point: given the two log lines, return the resolved SQL.
    """
    sql = extract_sql(preparing_line)
    params = extract_parameters(parameters_line)
    resolved = replace_placeholders(sql, params)
    if pretty:
        resolved = format_sql(resolved)
    return resolved


# ── Interactive CLI ──────────────────────────────────────────────────────────

def read_multiline(prompt: str) -> str:
    """Read input that may span multiple lines. Ends on an empty line."""
    print(prompt)
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if not line.strip() and lines:
            break
        lines.append(line)
    return "\n".join(lines)



def main():
    parser = argparse.ArgumentParser(
        description="Replace ? placeholders in MyBatis/JDBC debug log SQL with actual parameter values.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Interactive usage:\n"
            "  1. Run the script\n"
            "  2. Paste the 'Preparing:' log line (and optionally the 'Parameters:' line)\n"
            "  3. Press Enter twice to submit\n"
            "  4. Get the fully resolved, formatted SQL\n"
            "  5. Type 'quit' or 'q' to exit\n"
        ),
    )
    parser.add_argument(
        "--no-format", action="store_true",
        help="Disable SQL pretty-formatting (output single-line SQL)",
    )
    args = parser.parse_args()
    pretty = not args.no_format

    print("=" * 70)
    print("  SQL Parser — Replace ? placeholders with parameter values")
    print("=" * 70)
    print()

    while True:
        print("-" * 70)
        print("Paste both log lines (Preparing + Parameters), or just the Preparing line.")
        print("Press Enter twice when done. Type 'quit' or 'q' to exit.")
        print("-" * 70)

        raw = read_multiline("> ")

        if raw.strip().lower() in ("quit", "q", "exit"):
            print("Bye!")
            break

        if not raw.strip():
            continue

        # Try to detect if both lines are in the pasted text
        lines = [l.strip() for l in raw.strip().splitlines() if l.strip()]

        preparing_line = None
        parameters_line = None

        for line in lines:
            if "Preparing:" in line:
                preparing_line = line
            elif "Parameters:" in line:
                parameters_line = line

        if not preparing_line:
            print("\n[ERROR] Could not find a 'Preparing:' line in the input.\n")
            continue

        if not parameters_line:
            print("Paste the Parameters line (or press Enter if none):")
            parameters_line = input("> ").strip()
            if not parameters_line:
                parameters_line = "Parameters: "

        try:
            result = parse_and_replace(preparing_line, parameters_line, pretty=pretty)
            print("\n" + "=" * 70)
            print("  RESOLVED SQL")
            print("=" * 70)
            print(result)
            print("=" * 70 + "\n")
        except ValueError as e:
            print(f"\n[ERROR] {e}\n")


if __name__ == "__main__":
    main()
