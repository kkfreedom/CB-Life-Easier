"""Quick script to verify no threads are missed by the parser."""
import re
import sys
import argparse
sys.path.insert(0, ".")

import jstack_parser as jp

parser = argparse.ArgumentParser(description="Verify no threads are missed by jstack-parser.")
parser.add_argument("file", nargs="?", default=None, help="Path to the jstack output file")
args = parser.parse_args()

filepath = args.file
if not filepath:
    print("Usage: python jstack_verify.py <jstack_file>", file=sys.stderr)
    sys.exit(1)

# --- Count raw thread headers in the file ---
with open(filepath, "r", encoding="utf-8", errors="replace") as f:
    lines = f.readlines()

# A thread header starts with a quoted name: "thread-name"
RE_RAW_HEADER = re.compile(r'^"[^"]*"')
RE_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\s*$")
RE_FULL_DUMP = re.compile(r"^Full thread dump\s+")

raw_counts = {}  # timestamp -> list of thread header lines
current_ts = None
pending_ts = None

for line in lines:
    raw = line.rstrip("\n\r")
    m = RE_TIMESTAMP.match(raw)
    if m:
        pending_ts = raw.strip()
        continue
    m = RE_FULL_DUMP.match(raw)
    if m:
        current_ts = pending_ts or "unknown"
        if current_ts not in raw_counts:
            raw_counts[current_ts] = []
        pending_ts = None
        continue
    if current_ts and RE_RAW_HEADER.match(raw):
        raw_counts[current_ts].append(raw)

# --- Parse with our parser ---
dumps = jp.parse_jstack_file(filepath)

print("=" * 100)
print(f"{'Timestamp':<25s} {'Raw Headers':>12s} {'Parsed':>8s} {'Missed':>8s}")
print("-" * 100)

total_raw = 0
total_parsed = 0
all_missed = []

for dump in dumps:
    ts = dump.timestamp
    raw_list = raw_counts.get(ts, [])
    parsed_names = {t.name for t in dump.threads}
    
    # Extract names from raw headers
    raw_names = set()
    for hdr in raw_list:
        m = re.match(r'^"([^"]*)"', hdr)
        if m:
            raw_names.add(m.group(1))
    
    missed = raw_names - parsed_names
    extra = parsed_names - raw_names
    
    total_raw += len(raw_names)
    total_parsed += len(parsed_names)
    
    status = "OK" if not missed else "MISSED!"
    print(f"  {ts:<23s} {len(raw_names):>12d} {len(parsed_names):>8d} {len(missed):>8d}  {status}")
    
    if missed:
        all_missed.append((ts, missed, raw_list))
    if extra:
        print(f"    EXTRA (parsed but not in raw): {extra}")

print("-" * 100)
print(f"  {'TOTAL':<23s} {total_raw:>12d} {total_parsed:>8d} {total_raw - total_parsed:>8d}")
print("=" * 100)

# Show details of missed threads
if all_missed:
    print(f"\n{'!' * 80}")
    print("MISSED THREADS DETAIL:")
    print(f"{'!' * 80}")
    for ts, missed_names, raw_list in all_missed:
        print(f"\n  Timestamp: {ts}")
        for name in sorted(missed_names):
            # Find the raw header line for this name
            for hdr in raw_list:
                if hdr.startswith(f'"{name}"'):
                    print(f"    MISSED: {hdr[:150]}")
                    break
else:
    print("\nAll threads parsed successfully! No threads missed.")
