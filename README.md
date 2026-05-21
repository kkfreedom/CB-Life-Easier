# CB-Life-Easier

A collection of lightweight Python CLI tools for everyday backend debugging and troubleshooting.

> No external dependencies — all scripts run on **Python 3.10+** with the standard library only.

---

## Tools

| Script | Purpose | Docs |
|--------|---------|------|
| [`sql_parser.py`](sql_parser.py) | Resolve MyBatis / JDBC log `?` placeholders into executable SQL | [README](sql_parser-README.md) |
| [`jstack_parser.py`](jstack_parser.py) | Parse & analyze jstack thread dumps — CPU ranking, state distribution, delta analysis | [README](jstack_parser-README.md) |
| [`jstack_verify.py`](jstack_verify.py) | Verify that `jstack_parser.py` captures every thread in a dump file | [README](jstack_verify-README.md) |

---

## Quick Start

### sql_parser — SQL Log Resolver

Paste MyBatis/JDBC `Preparing:` + `Parameters:` log lines and get a fully resolved, pretty-formatted SQL query.

```bash
python sql_parser.py
```

```
> ==>  Preparing: SELECT * FROM users WHERE id = ? AND name = ?
> ==> Parameters: 42(Integer), Alice(String)

SELECT *
FROM users
WHERE id = 42
    AND name = 'Alice'
```

### jstack_parser — Thread Dump Analyzer

Analyze jstack output files to find the highest CPU-consuming threads, view state distributions, and compute CPU deltas across multiple dumps.

```bash
python jstack_parser.py <jstack_file>
python jstack_parser.py <jstack_file> --top 20
python jstack_parser.py <jstack_file> --state RUNNABLE -o results.txt
```

### jstack_verify — Parser Accuracy Checker

Cross-check that no threads are missed during parsing.

```bash
python jstack_verify.py <jstack_file>
```

---

## Requirements

- **Python 3.10+**
- No external dependencies — stdlib only
