#!/usr/bin/env python3
"""Debug script: Parse and reconstruct without translation to verify pipeline."""

import sys

sys.path.insert(0, "/Users/zhengcaiyi/Desktop/博0/杂项/写点小玩意/iee翻译/ieeA/src")

from ieeA.parser.latex_parser import LaTeXParser

# Parse the original file
parser = LaTeXParser()
doc = parser.parse_file(
    "/Users/zhengcaiyi/Desktop/博0/杂项/写点小玩意/iee翻译/ieeA/output/hq/2511.16709/neurips_2025.tex"
)

print(f"=== Parse Results ===")
print(f"Total chunks: {len(doc.chunks)}")
print(f"Global placeholders: {len(doc.global_placeholders)}")
print(f"Body template length: {len(doc.body_template)}")

# Reconstruct without translation (pass None)
reconstructed = doc.reconstruct(translated_chunks=None)

# Write to debug file
output_path = "/Users/zhengcaiyi/Desktop/博0/杂项/写点小玩意/iee翻译/ieeA/output/hq/2511.16709/debug_reconstructed.tex"
with open(output_path, "w", encoding="utf-8") as f:
    f.write(reconstructed)

print(f"\nReconstructed file written to: {output_path}")
print(f"Reconstructed length: {len(reconstructed)} chars")

# Compare with original
original_path = "/Users/zhengcaiyi/Desktop/博0/杂项/写点小玩意/iee翻译/ieeA/output/hq/2511.16709/neurips_2025.tex"
with open(original_path, "r", encoding="utf-8") as f:
    original = f.read()

print(f"Original length: {len(original)} chars")

# Check for remaining placeholders
import re

chunk_placeholders = re.findall(r"\{\{CHUNK_[a-f0-9-]+\}\}", reconstructed)
global_placeholders = re.findall(r"\[\[[A-Z_]+_\d+\]\]", reconstructed)

print(f"\n=== Remaining Placeholders in Reconstructed ===")
print(f"CHUNK placeholders: {len(chunk_placeholders)}")
print(f"Global placeholders: {len(global_placeholders)}")

if chunk_placeholders:
    print(f"\nUnreplaced CHUNK placeholders (first 10):")
    for p in chunk_placeholders[:10]:
        print(f"  {p}")

if global_placeholders:
    print(f"\nUnreplaced global placeholders (first 10):")
    for p in global_placeholders[:10]:
        print(f"  {p}")

print(f"\n=== Correct Chunk Analysis (Metis Review) ===")
chunk_ids_in_preamble = set(re.findall(r"\{\{CHUNK_([a-f0-9-]+)\}\}", doc.preamble))
chunk_ids_in_body = set(re.findall(r"\{\{CHUNK_([a-f0-9-]+)\}\}", doc.body_template))
author_placeholders_in_body = re.findall(r"\[\[AUTHOR_\d+\]\]", doc.body_template)
chunk_ids_created = set(c.id for c in doc.chunks)

total_placeholders = (
    len(chunk_ids_in_preamble)
    + len(chunk_ids_in_body)
    + len(author_placeholders_in_body)
)

print(f"Chunks created: {len(chunk_ids_created)}")
print(f"  - CHUNK placeholders in preamble: {len(chunk_ids_in_preamble)}")
print(f"  - CHUNK placeholders in body_template: {len(chunk_ids_in_body)}")
print(f"  - AUTHOR placeholders in body_template: {len(author_placeholders_in_body)}")
print(f"Total placeholders: {total_placeholders}")
print(f"Match: {len(chunk_ids_created) == total_placeholders}")

all_placeholder_ids = chunk_ids_in_preamble | chunk_ids_in_body
missing_in_template = chunk_ids_created - all_placeholder_ids
protected_chunks = [c for c in doc.chunks if c.context == "protected"]
missing_non_protected = missing_in_template - set(c.id for c in protected_chunks)

if missing_non_protected:
    print(f"\n*** REAL Orphan Chunks (not protected): {len(missing_non_protected)} ***")
    for cid in list(missing_non_protected)[:10]:
        chunk = next(c for c in doc.chunks if c.id == cid)
        print(f"  ID: {cid[:8]}... context: {chunk.context}")
        print(f"    content: {chunk.content[:80]}...")
else:
    print(
        f"\nNo orphan chunks found (all accounted for in preamble + body + protected)"
    )
