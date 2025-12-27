#!/usr/bin/env python3
"""
Test script to run all components of the Micro-CDN system.
Run this script to start all servers and perform a test download.
"""

import subprocess
import time
import sys
import os

# Get the directory where this script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON = sys.executable

def main():
    print("=" * 60)
    print("  Micro-CDN System Test")
    print("=" * 60)
    print()
    
    processes = []
    
    try:
        # Step 1: Start Monitor Server
        print("[1/4] Starting Monitor Server...")
        monitor = subprocess.Popen(
            [PYTHON, os.path.join(SCRIPT_DIR, "monitor_server.py")],
            cwd=SCRIPT_DIR
        )
        processes.append(("Monitor Server", monitor))
        time.sleep(1)
        
        # Step 2: Start Index Server
        print("[2/4] Starting Index Server...")
        index = subprocess.Popen(
            [PYTHON, os.path.join(SCRIPT_DIR, "index_server.py")],
            cwd=SCRIPT_DIR
        )
        processes.append(("Index Server", index))
        time.sleep(1)
        
        # Step 3: Start Content Server 1
        print("[3/4] Starting Content Server 1...")
        cs1 = subprocess.Popen(
            [PYTHON, os.path.join(SCRIPT_DIR, "content_server.py"),
             "--id", "CS1", "--tcp-port", "7001", "--udp-port", "7002",
             "--files-dir", os.path.join(SCRIPT_DIR, "files_CS1")],
            cwd=SCRIPT_DIR
        )
        processes.append(("Content Server 1", cs1))
        time.sleep(1)
        
        # Step 4: Start Content Server 2
        print("[4/4] Starting Content Server 2...")
        cs2 = subprocess.Popen(
            [PYTHON, os.path.join(SCRIPT_DIR, "content_server.py"),
             "--id", "CS2", "--tcp-port", "7101", "--udp-port", "7102",
             "--files-dir", os.path.join(SCRIPT_DIR, "files_CS2")],
            cwd=SCRIPT_DIR
        )
        processes.append(("Content Server 2", cs2))
        time.sleep(2)
        
        print()
        print("=" * 60)
        print("  All servers are running!")
        print("=" * 60)
        print()
        print("You can now run the client in a separate terminal:")
        print()
        print(f"  Interactive mode: {PYTHON} client.py -i")
        print(f"  List files:       {PYTHON} client.py --list")
        print(f"  Download file:    {PYTHON} client.py shared_document.txt")
        print()
        print("Press Ctrl+C to stop all servers...")
        print()
        
        # Wait for user interrupt
        while True:
            time.sleep(1)
            # Check if any process died
            for name, proc in processes:
                if proc.poll() is not None:
                    print(f"Warning: {name} has stopped!")
                    
    except KeyboardInterrupt:
        print()
        print("Shutting down all servers...")
        
    finally:
        # Stop all processes
        for name, proc in processes:
            if proc.poll() is None:
                print(f"Stopping {name}...")
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    
        print("All servers stopped.")


if __name__ == "__main__":
    main()
