# SQL Parser

Resolves MyBatis / JDBC debug log output into executable SQL by replacing `?` placeholders with actual parameter values. The output is pretty-formatted with proper indentation.

## Quick Start

```bash
python SQL-parser.py
```

Paste your log lines when prompted, press **Enter twice** to submit, and get the resolved SQL.

## Usage

### Interactive Mode

```
======================================================================
  SQL Parser — Replace ? placeholders with parameter values
======================================================================

----------------------------------------------------------------------
Paste both log lines (Preparing + Parameters), or just the Preparing line.
Press Enter twice when done. Type 'quit' or 'q' to exit.
----------------------------------------------------------------------
>
```

You can paste **both lines at once** — the tool auto-detects which is which:

```
==>  Preparing: SELECT * FROM users WHERE id = ? AND name = ? AND status = ?
==> Parameters: 42(Integer), Alice(String), null
```

Or paste just the `Preparing:` line and you'll be prompted for the `Parameters:` line separately.

### Example Output

**Input:**
```
==>  Preparing: SELECT u.id, u.name FROM users u INNER JOIN roles r ON r.user_id = u.id WHERE u.status = ? AND r.role_name = ? ORDER BY u.name
==> Parameters: activated(String), admin(String)
```

**Output:**
```sql
SELECT u.id, u.name
FROM users u
INNER JOIN roles r
    ON r.user_id = u.id
WHERE u.status = 'activated'
    AND r.role_name = 'admin'
ORDER BY u.name
```

## Features

### Parameter Type Handling

| Type | Formatting | Example |
|------|-----------|---------|
| `String`, `Varchar`, `Char`, `Text` | Wrapped in single quotes | `'Alice'` |
| `Date`, `Timestamp`, `Time` | Wrapped in single quotes | `'2026-05-21'` |
| `Integer`, `Long`, `BigDecimal`, `Float`, `Double` | As-is (no quotes) | `42` |
| `Null` / `null` | Replaced with `NULL` | `NULL` |
| Unknown type | Wrapped in single quotes (safe default) | `'value'` |

### SQL Formatting

- **Keyword newlines** — Major clauses (`SELECT`, `FROM`, `WHERE`, `JOIN`, etc.) start on new lines
- **Sub-clause indentation** — `AND`, `OR`, `ON` are indented one level under their parent clause
- **Multi-word keywords** — `INNER JOIN`, `ORDER BY`, `LEFT OUTER JOIN`, etc. stay on one line
- **Subquery indentation** — Content inside `(...)` subqueries is automatically indented

### Supported SQL Statements

- `SELECT` queries (including subqueries, `UNION`, `UNION ALL`)
- `INSERT INTO ... VALUES`
- `UPDATE ... SET ... WHERE`
- `DELETE FROM ... WHERE`

## Programmatic Usage

You can import the functions directly:

```python
from SQL-parser import parse_and_replace, format_sql

# From log lines
preparing = "==>  Preparing: SELECT * FROM users WHERE id = ?"
parameters = "==> Parameters: 42(Integer)"
result = parse_and_replace(preparing, parameters)
print(result)

# Format any SQL string
raw_sql = "SELECT a, b FROM t1 INNER JOIN t2 ON t1.id = t2.id WHERE a = 1"
print(format_sql(raw_sql))

# Get unformatted (single-line) output
result = parse_and_replace(preparing, parameters, pretty=False)
```

## Requirements

- Python 3.10+ (uses `list[tuple]` type hints)
- No external dependencies — stdlib only (`re`, `sys`)
