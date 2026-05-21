# jstack_verify — Parser Accuracy Checker

A validation script that cross-checks the `jstack_parser.py` output against raw thread headers in the input file to ensure no threads are missed during parsing.

## Quick Start

```bash
python jstack_verify.py <jstack_file>
```

**Example:**
```bash
python jstack_verify.py 2.2.1.2-jstack.txt
```

## What It Does

1. **Counts raw thread headers** — Scans the jstack file independently using a simple regex (`"thread-name"` pattern) to find every thread entry
2. **Parses with jstack_parser** — Runs the same file through `jstack_parser.py`
3. **Compares results** — For each dump timestamp, reports how many threads were found raw vs. parsed, and flags any discrepancies

## Output

### Summary Table

```
====================================================================================================
Timestamp                 Raw Headers   Parsed   Missed
----------------------------------------------------------------------------------------------------
  2026-05-07 12:47:38              142      142        0  OK
  2026-05-07 12:48:38              142      142        0  OK
----------------------------------------------------------------------------------------------------
  TOTAL                            284      284        0
====================================================================================================

All threads parsed successfully! No threads missed.
```

### When Threads Are Missed

If the parser fails to capture some threads, the script prints detailed info:

```
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
MISSED THREADS DETAIL:
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

  Timestamp: 2026-05-07 12:47:38
    MISSED: "some-thread-name" #99 daemon prio=5 os_prio=0 cpu=...
```

This helps identify thread header formats that the parser's regex doesn't handle, so the regex can be updated.

## Requirements

- Python 3.10+
- `jstack_parser.py` must be in the same directory
- No external dependencies
