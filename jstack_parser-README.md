# jstack Thread Dump Analyzer

Parses `jstack` output files containing one or more thread dumps, structures the data, and produces a report sorted by CPU time — useful for identifying high-CPU threads during Java performance troubleshooting.

## Quick Start

```bash
python jstack_parser.py <jstack_file>
```

## CLI Options

| Option | Description | Default |
|--------|-------------|---------|
| `file` | Path to the jstack output file | *(required)* |
| `--top N` | Show only the top N threads by CPU time (0 = all) | `0` (all) |
| `--state STATE` | Filter threads by state (e.g. `RUNNABLE`, `WAITING`) | *(none)* |
| `-o, --output FILE` | Write results to a file instead of stdout | *(stdout)* |

## Usage Examples

```bash
# Full report, all threads
python jstack_parser.py dump.txt

# Top 20 threads by CPU
python jstack_parser.py dump.txt --top 20

# Only RUNNABLE threads
python jstack_parser.py dump.txt --state RUNNABLE

# Top 10 RUNNABLE threads, saved to file
python jstack_parser.py dump.txt --top 10 --state RUNNABLE -o results.txt
```

## Input Format

The tool expects standard `jstack` output, optionally with multiple dumps in one file. Each dump is identified by:

```
2026-05-07 12:47:38                         ← timestamp (optional)
Full thread dump Java HotSpot(TM) ...       ← dump header

"http-nio-8080-exec-1" #33 daemon prio=5 os_prio=0 cpu=1234.56ms elapsed=99.12s tid=0x... nid=0x... runnable  [0x...]
   java.lang.Thread.State: RUNNABLE
        at java.net.SocketInputStream.read(...)
        ...
```

## Report Output

### 1. Per-Dump Summary

For each thread dump found:

- **Timestamp** and **VM info**
- **Thread count**
- **Thread state distribution** — visual bar chart of states (`RUNNABLE`, `WAITING`, `TIMED_WAITING`, etc.)
- **Thread table** — sorted by CPU time descending

```
================================================================================
  Timestamp : 2026-05-07 12:47:38
  VM Info   : Java HotSpot(TM) 64-Bit Server VM (17.0.2+8-86)
  Threads   : 142
================================================================================

  Thread State Distribution:
    WAITING (parking)                          58  ##########...
    TIMED_WAITING (parking)                    34  ######...
    RUNNABLE                                   28  #####...

  Rank        CPU    Elapsed   Avg CPU% State                          Name
  ----        ---    -------   -------- -----                          ----
  1       521.30s   2075062.6s    0.03% RUNNABLE                       catalina-exec-12
  2       412.87s   2075062.6s    0.02% RUNNABLE                       catalina-exec-5
  ...
```

### 2. CPU Delta Analysis

When **multiple dumps** are present, the tool calculates per-thread CPU consumption *between* consecutive dumps — the key metric for finding threads actively burning CPU:

```
------------------------------------------------------------------------------------------------------------------------
  CPU Delta: 2026-05-07 12:47:38  -->  2026-05-07 12:48:38
------------------------------------------------------------------------------------------------------------------------

  Rank    CPU Delta  Interval%    Total CPU   Avg CPU% State                          Name
  ----    ---------  ---------    ---------   -------- -----                          ----
  1          2.45s      4.08%      521.30s      0.03% RUNNABLE                       catalina-exec-12
  2          1.87s      3.12%      412.87s      0.02% RUNNABLE                       catalina-exec-5
  ...
```

## Parsed Thread Metadata

Each thread entry captures:

| Field | Description |
|-------|-------------|
| `name` | Thread name |
| `daemon` | Whether it's a daemon thread |
| `cpu_ms` | Cumulative CPU time in milliseconds |
| `elapsed_s` | Wall-clock elapsed time in seconds |
| `thread_state` | Java thread state (e.g. `RUNNABLE`, `WAITING (parking)`) |
| `tid` / `nid` | Thread ID / Native thread ID |
| `locks_held` | Lock addresses currently held |
| `locks_waiting` | Lock addresses being waited on |
| `stack_lines` | Full stack trace |

## Metrics Calculated

| Metric | Formula | Use case |
|--------|---------|----------|
| **Avg CPU %** | `cpu_ms / (elapsed_s × 1000) × 100` | Lifetime average CPU utilization |
| **CPU Delta** | `current_cpu_ms − previous_cpu_ms` | CPU consumed in the interval between dumps |
| **Interval %** | `cpu_delta / (elapsed_delta × 1000) × 100` | CPU utilization during the specific interval |

## Requirements

- Python 3.10+
- No external dependencies — stdlib only (`re`, `sys`, `argparse`, `dataclasses`)
