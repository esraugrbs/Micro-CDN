#!/usr/bin/env python3
"""Start Content Server 2"""
import subprocess
import sys
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

subprocess.run([
    sys.executable,
    os.path.join(SCRIPT_DIR, "content_server.py"),
    "--id", "CS2",
    "--tcp-port", "7101",
    "--udp-port", "7102",
    "--files-dir", os.path.join(SCRIPT_DIR, "files_CS2")
])
