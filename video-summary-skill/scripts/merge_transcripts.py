#!/usr/bin/env python3
"""Merge chunk transcripts with time offsets into a single transcript."""
import re, os, sys

CHUNKS_DIR = sys.argv[1] if len(sys.argv) > 1 else "_chunks"
OUTPUT_DIR = sys.argv[2] if len(sys.argv) > 2 else "."
TOTAL_SECONDS = int(sys.argv[3]) if len(sys.argv) > 3 else 0
NUM_CHUNKS = int(sys.argv[4]) if len(sys.argv) > 4 else 4

if TOTAL_SECONDS == 0:
    for i in range(NUM_CHUNKS):
        t_file = os.path.join(CHUNKS_DIR, f"chunk_{i:02d}_transcript.txt")
        if os.path.exists(t_file):
            with open(t_file) as f:
                lines_list = f.readlines()
            if lines_list:
                last = lines_list[-1]
                m = re.match(r"\[(\d+):(\d+)\]", last)
                if m:
                    TOTAL_SECONDS = int(m.group(1)) * 60 + int(m.group(2))
            break

chunk_dur = TOTAL_SECONDS // NUM_CHUNKS

merged = []
full_merged = []

for i in range(NUM_CHUNKS):
    offset = i * chunk_dur
    t_file = os.path.join(CHUNKS_DIR, f"chunk_{i:02d}_transcript.txt")
    f_file = os.path.join(CHUNKS_DIR, f"chunk_{i:02d}_full.txt")

    if os.path.exists(t_file):
        for line in open(t_file):
            m = re.match(r"\[(\d+):(\d+)\]\s*(.*)", line)
            if m:
                total_sec = int(m.group(1)) * 60 + int(m.group(2)) + offset
                merged.append(f"[{total_sec//60}:{total_sec%60:02d}] {m.group(3)}")

    if os.path.exists(f_file):
        full_merged.append(open(f_file).read())

NL = chr(10)
with open(os.path.join(OUTPUT_DIR, "transcript.txt"), "w") as f:
    f.write(NL.join(merged) + NL)
with open(os.path.join(OUTPUT_DIR, "transcript_full.txt"), "w") as f:
    f.write(" ".join(full_merged))

print(f"Merged: {len(merged)} segments -> {OUTPUT_DIR}/transcript.txt")
print(f"Full text: {sum(len(x) for x in full_merged)} chars -> {OUTPUT_DIR}/transcript_full.txt")
