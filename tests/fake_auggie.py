#!/usr/bin/env python3
"""Simple fake Auggie CLI for testing."""

import argparse
import sys

parser = argparse.ArgumentParser(description="Fake Auggie CLI")
parser.add_argument("instr", nargs="*", help="Remaining args")
parser.add_argument("--print", dest="instruction")
parser.add_argument("--compact", action="store_true")
parser.add_argument("--github-api-token")

# We can't use argparse default parsing for repeated options easily, so parse manually.

args_iter = iter(sys.argv[1:])
compact = False
github_token = None
instruction = None
extra = []
for arg in args_iter:
    if arg == "--compact":
        compact = True
    elif arg == "--github-api-token":
        github_token = next(args_iter, None)
    elif arg == "--print":
        instruction = next(args_iter, "")
    else:
        extra.append(arg)

context = sys.stdin.read()

print("[fake-auggie]")
print(f"Instruction: {instruction}")
print(f"Compact: {compact}")
if github_token:
    print(f"GitHub token: {github_token}")
if extra:
    print(f"Extra args: {' '.join(extra)}")
if context.strip():
    print("Context:\n" + context)
else:
    print("(no context provided)")
