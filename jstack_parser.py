#!/usr/bin/env python3
"""
jstack Thread Dump Analyzer
============================
Parses jstack output files that may contain multiple thread dumps (each
preceded by a timestamp line), structures the data, and prints a summary
sorted by CPU time in descending order, grouped by dump timestamp.

Usage:
    python jstack_parser.py <jstack_file>
    python jstack_parser.py <jstack_file> --top 20
    python jstack_parser.py <jstack_file> --state RUNNABLE
"""

import re
import sys
import io
import argparse
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class ThreadInfo:
    """Represents a single thread entry in a jstack dump."""
    name: str = ""
    daemon: bool = False
    priority: int = -1
    os_priority: int = -1
    cpu_ms: float = 0.0          # cpu time in milliseconds
    elapsed_s: float = 0.0       # elapsed time in seconds
    tid: str = ""
    nid: str = ""
    thread_state_short: str = "" # e.g. "runnable", "waiting on condition"
    thread_state: str = ""       # e.g. "RUNNABLE", "WAITING (parking)"
    stack_lines: List[str] = field(default_factory=list)
    locks_held: List[str] = field(default_factory=list)
    locks_waiting: List[str] = field(default_factory=list)
    raw_header: str = ""


@dataclass
class ThreadDump:
    """One complete thread dump captured at a specific timestamp."""
    timestamp: str = ""
    vm_info: str = ""
    threads: List[ThreadInfo] = field(default_factory=list)
    jni_global_refs: Optional[int] = None


# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# Matches a timestamp line like "2026-05-07 12:47:38"
RE_TIMESTAMP = re.compile(r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s*$")

# Matches the "Full thread dump ..." line
RE_FULL_DUMP = re.compile(r"^Full thread dump\s+(.*)$")

# Matches the thread header line, e.g.:
#   "http-nio-8080-exec-1" #33 daemon prio=5 os_prio=0 cpu=1234.56ms elapsed=99.12s tid=0x... nid=0x... runnable  [0x...]
#   "catalina-exec-12" #313 [4396] daemon prio=5 os_prio=0 cpu=521297703.13ms elapsed=2075062.63s tid=0x... nid=4396 runnable  [0x...]
RE_THREAD_HEADER = re.compile(
    r'^"(?P<name>[^"]*)"'           # thread name in quotes
    r'(?:\s+#\d+)?'                 # optional internal thread number
    r'(?:\s+\[\d+\])?'              # optional [os_thread_id] bracket
    r'(?:\s+daemon)?'               # optional daemon flag
    r'(?:\s+prio=(?P<prio>\d+))?'   # optional priority
    r'(?:\s+os_prio=(?P<osprio>[\-\d]+))?' # optional OS priority
    r'(?:\s+cpu=(?P<cpu>[\d.]+)ms)?'       # optional cpu time
    r'(?:\s+elapsed=(?P<elapsed>[\d.]+)s)?' # optional elapsed time
    r'(?:\s+tid=(?P<tid>0x[0-9a-fA-F]+))?' # optional tid
    r'(?:\s+nid=(?P<nid>(?:0x)?[0-9a-fA-F]+))?' # optional nid (hex or decimal)
    r'(?:\s+(?P<state_short>[^\[]+?))?'     # short state description
    r'(?:\s+\[(?P<addr>0x[0-9a-fA-F]+)\])?' # optional address
    r'\s*$'
)

# Matches "   java.lang.Thread.State: RUNNABLE"
RE_THREAD_STATE = re.compile(r"^\s+java\.lang\.Thread\.State:\s+(.+)$")

# Matches JNI global references line
RE_JNI_REFS = re.compile(r"^JNI global ref(?:erence)?s?:\s*(\d+)", re.IGNORECASE)

# Lock patterns
RE_LOCK_HELD = re.compile(r"^\s+-\s+locked\s+<(.+?)>")
RE_LOCK_WAITING = re.compile(r"^\s+-\s+(?:waiting to lock|waiting on|parking to wait for)\s+<(.+?)>")


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def parse_jstack_file(filepath: str) -> List[ThreadDump]:
    """Parse a jstack file and return a list of ThreadDump objects."""
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    dumps: List[ThreadDump] = []
    current_dump: Optional[ThreadDump] = None
    current_thread: Optional[ThreadInfo] = None
    pending_timestamp: Optional[str] = None

    def _flush_thread():
        nonlocal current_thread
        if current_thread and current_dump:
            current_dump.threads.append(current_thread)
            current_thread = None

    for line in lines:
        raw = line.rstrip("\n\r")

        # --- Timestamp line ---
        m = RE_TIMESTAMP.match(raw)
        if m:
            pending_timestamp = m.group(1)
            continue

        # --- Full thread dump header ---
        m = RE_FULL_DUMP.match(raw)
        if m:
            _flush_thread()
            current_dump = ThreadDump(
                timestamp=pending_timestamp or "",
                vm_info=m.group(1).strip(),
            )
            dumps.append(current_dump)
            pending_timestamp = None
            continue

        if current_dump is None:
            continue

        # --- JNI global references ---
        m = RE_JNI_REFS.match(raw)
        if m:
            _flush_thread()
            current_dump.jni_global_refs = int(m.group(1))
            continue

        # --- Thread header ---
        m = RE_THREAD_HEADER.match(raw)
        if m:
            _flush_thread()
            current_thread = ThreadInfo(
                name=m.group("name"),
                daemon="daemon" in raw,
                priority=int(m.group("prio")) if m.group("prio") else -1,
                os_priority=int(m.group("osprio")) if m.group("osprio") else -1,
                cpu_ms=float(m.group("cpu")) if m.group("cpu") else 0.0,
                elapsed_s=float(m.group("elapsed")) if m.group("elapsed") else 0.0,
                tid=m.group("tid") or "",
                nid=m.group("nid") or "",
                thread_state_short=(m.group("state_short") or "").strip(),
                raw_header=raw,
            )
            continue

        # --- Thread state line ---
        if current_thread:
            m = RE_THREAD_STATE.match(raw)
            if m:
                current_thread.thread_state = m.group(1).strip()
                continue

            # Stack trace / lock lines
            if raw.startswith("\t") or raw.startswith("   "):
                current_thread.stack_lines.append(raw)

                lm = RE_LOCK_HELD.match(raw)
                if lm:
                    current_thread.locks_held.append(lm.group(1))

                lm = RE_LOCK_WAITING.match(raw)
                if lm:
                    current_thread.locks_waiting.append(lm.group(1))

        # Blank line ends current thread block
        if raw.strip() == "":
            _flush_thread()

    # flush any remaining thread
    _flush_thread()

    return dumps


# ---------------------------------------------------------------------------
# Analysis helpers
# ---------------------------------------------------------------------------

def calc_avg_cpu_pct(cpu_ms: float, elapsed_s: float) -> float:
    """Calculate average CPU usage as a percentage: (cpu_ms / elapsed_ms) * 100."""
    if elapsed_s <= 0:
        return 0.0
    return (cpu_ms / (elapsed_s * 1000)) * 100


def build_thread_map(dump: ThreadDump) -> Dict[str, ThreadInfo]:
    """Build a lookup dict from thread name -> ThreadInfo for a dump."""
    result: Dict[str, ThreadInfo] = {}
    for t in dump.threads:
        result[t.name] = t
    return result


@dataclass
class ThreadDelta:
    """CPU delta for a single thread between two consecutive dumps."""
    name: str
    cpu_delta_ms: float        # CPU time consumed in the interval
    elapsed_delta_s: float     # wall-clock time of the interval
    interval_cpu_pct: float    # cpu_delta / elapsed_delta as %
    state: str                 # thread state in the later dump
    cumulative_cpu_ms: float   # total cpu at the later dump
    cumulative_avg_pct: float  # overall avg cpu%


def compute_deltas(prev: ThreadDump, curr: ThreadDump) -> List[ThreadDelta]:
    """Compute per-thread CPU deltas between two consecutive dumps."""
    prev_map = build_thread_map(prev)
    deltas: List[ThreadDelta] = []

    for t in curr.threads:
        prev_t = prev_map.get(t.name)
        if prev_t is None:
            # New thread -- treat full cpu as delta
            cpu_delta = t.cpu_ms
            elapsed_delta = t.elapsed_s
        else:
            cpu_delta = t.cpu_ms - prev_t.cpu_ms
            elapsed_delta = t.elapsed_s - prev_t.elapsed_s

        if cpu_delta < 0:
            cpu_delta = 0.0  # guard against counter reset

        interval_pct = (cpu_delta / (elapsed_delta * 1000)) * 100 if elapsed_delta > 0 else 0.0
        cumulative_pct = calc_avg_cpu_pct(t.cpu_ms, t.elapsed_s)
        state = t.thread_state or t.thread_state_short or "-"

        deltas.append(ThreadDelta(
            name=t.name,
            cpu_delta_ms=cpu_delta,
            elapsed_delta_s=elapsed_delta,
            interval_cpu_pct=interval_pct,
            state=state,
            cumulative_cpu_ms=t.cpu_ms,
            cumulative_avg_pct=cumulative_pct,
        ))

    return deltas


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def format_cpu(ms: float) -> str:
    """Format milliseconds into a human-friendly string."""
    if ms >= 1000:
        return f"{ms / 1000:.2f}s"
    return f"{ms:.2f}ms"


def format_pct(pct: float) -> str:
    """Format a percentage value."""
    if pct >= 10:
        return f"{pct:.1f}%"
    return f"{pct:.2f}%"


def print_dump_summary(dump: ThreadDump, top_n: int = 0, state_filter: str = "", file=None):
    """Print a structured summary of a single thread dump."""
    out = file or sys.stdout
    separator = "=" * 80
    print(f"\n{separator}", file=out)
    print(f"  Timestamp : {dump.timestamp}", file=out)
    print(f"  VM Info   : {dump.vm_info}", file=out)
    print(f"  Threads   : {len(dump.threads)}", file=out)
    if dump.jni_global_refs is not None:
        print(f"  JNI Refs  : {dump.jni_global_refs}", file=out)
    print(separator, file=out)

    # --- State distribution ---
    state_counts: dict = {}
    for t in dump.threads:
        st = t.thread_state or t.thread_state_short or "UNKNOWN"
        state_counts[st] = state_counts.get(st, 0) + 1

    print("\n  Thread State Distribution:", file=out)
    for st, cnt in sorted(state_counts.items(), key=lambda x: -x[1]):
        bar = "#" * cnt
        print(f"    {st:<40s} {cnt:>4d}  {bar}", file=out)

    # --- Sort by CPU desc ---
    threads = sorted(dump.threads, key=lambda t: t.cpu_ms, reverse=True)

    # optional filters
    if state_filter:
        upper = state_filter.upper()
        threads = [t for t in threads if upper in (t.thread_state or "").upper()]

    if top_n > 0:
        threads = threads[:top_n]

    print(f"\n  {'Rank':<6s} {'CPU':>10s} {'Elapsed':>10s} {'Avg CPU%':>10s} {'State':<30s} {'Name'}", file=out)
    print(f"  {'----':<6s} {'---':>10s} {'-------':>10s} {'--------':>10s} {'-----':<30s} {'----'}", file=out)

    for idx, t in enumerate(threads, start=1):
        state = t.thread_state or t.thread_state_short or "-"
        elapsed = f"{t.elapsed_s:.1f}s" if t.elapsed_s > 0 else "-"
        avg_pct = format_pct(calc_avg_cpu_pct(t.cpu_ms, t.elapsed_s))
        print(f"  {idx:<6d} {format_cpu(t.cpu_ms):>10s} {elapsed:>10s} {avg_pct:>10s} {state:<30s} {t.name}", file=out)

    print(file=out)


def print_delta_report(prev: ThreadDump, curr: ThreadDump, top_n: int = 10, file=None):
    """Print the top CPU-consuming threads between two consecutive dumps."""
    out = file or sys.stdout
    deltas = compute_deltas(prev, curr)
    deltas.sort(key=lambda d: d.cpu_delta_ms, reverse=True)

    shown = deltas[:top_n] if top_n > 0 else deltas

    separator = "-" * 120
    print(f"\n{separator}", file=out)
    print(f"  CPU Delta: {prev.timestamp}  -->  {curr.timestamp}", file=out)
    print(separator, file=out)

    print(f"\n  {'Rank':<6s} {'CPU Delta':>12s} {'Interval%':>10s} {'Total CPU':>12s} {'Avg CPU%':>10s} {'State':<30s} {'Name'}", file=out)
    print(f"  {'----':<6s} {'----------':>12s} {'---------':>10s} {'---------':>12s} {'--------':>10s} {'-----':<30s} {'----'}", file=out)

    for idx, d in enumerate(shown, start=1):
        print(
            f"  {idx:<6d}"
            f" {format_cpu(d.cpu_delta_ms):>12s}"
            f" {format_pct(d.interval_cpu_pct):>10s}"
            f" {format_cpu(d.cumulative_cpu_ms):>12s}"
            f" {format_pct(d.cumulative_avg_pct):>10s}"
            f" {d.state:<30s}"
            f" {d.name}",
            file=out,
        )

    print(file=out)


def print_full_report(dumps: List[ThreadDump], top_n: int = 0, state_filter: str = "", file=None):
    """Print the full report for all dumps found in the file."""
    out = file or sys.stdout
    print(f"\n{'#' * 80}", file=out)
    print(f"  jstack Analyzer -- found {len(dumps)} thread dump(s)", file=out)
    print(f"{'#' * 80}", file=out)

    # --- Per-dump summary ---
    for dump in dumps:
        print_dump_summary(dump, top_n=top_n, state_filter=state_filter, file=out)

    # --- Delta analysis (consecutive pairs) ---
    if len(dumps) >= 2:
        print(f"\n{'#' * 120}", file=out)
        print(f"  CPU DELTA ANALYSIS  (top 10 threads by CPU consumed per interval)", file=out)
        print(f"{'#' * 120}", file=out)

        for i in range(1, len(dumps)):
            print_delta_report(dumps[i - 1], dumps[i], top_n=10, file=out)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Analyze jstack thread dump files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("file", help="Path to the jstack output file")
    parser.add_argument(
        "--top", type=int, default=0,
        help="Show only the top N threads by CPU time (0 = all)",
    )
    parser.add_argument(
        "--state", type=str, default="",
        help="Filter threads by state (e.g. RUNNABLE, WAITING)",
    )
    parser.add_argument(
        "-o", "--output", type=str, default="",
        help="Write results to the specified file (UTF-8 encoded)",
    )
    args = parser.parse_args()

    try:
        dumps = parse_jstack_file(args.file)
    except FileNotFoundError:
        print(f"Error: file not found -- {args.file}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error parsing file: {e}", file=sys.stderr)
        sys.exit(1)

    if not dumps:
        print("No thread dumps found in the file.", file=sys.stderr)
        sys.exit(1)

    out_file = None
    try:
        if args.output:
            out_file = open(args.output, "w", encoding="utf-8")
        print_full_report(dumps, top_n=args.top, state_filter=args.state, file=out_file)
        if args.output:
            print(f"Results written to: {args.output}")
    finally:
        if out_file:
            out_file.close()


if __name__ == "__main__":
    main()
