#!/usr/bin/env python3
import sys, json, os

try:
    cwd = json.load(sys.stdin).get('cwd', os.getcwd())
except Exception:
    cwd = os.getcwd()

wip = os.path.join(cwd, 'WIP.md')
if os.path.exists(wip):
    with open(wip) as f:
        content = f.read().strip()
    if content:
        print(f"## WIP Session Handoff\n\n{content}\n")
