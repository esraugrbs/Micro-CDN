#!/usr/bin/env python3
"""Start Content Server 1"""
import subprocess
import sys
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

subprocess.run([
    sys.executable,
    os.path.join(SCRIPT_DIR, "content_server.py"),
    "--id", "CS1",
    "--tcp-port", "7001",
    "--udp-port", "7002",
    "--files-dir", os.path.join(SCRIPT_DIR, "files_CS1")
])
