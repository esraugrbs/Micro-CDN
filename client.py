#!/usr/bin/env python3
"""
Client Program for Micro-CDN
- Contacts Index Server to locate files
- Downloads files from Content Servers
"""

import socket
import sys
import argparse
import os
from datetime import datetime

# Configuration
INDEX_SERVER_HOST = 'localhost'
INDEX_SERVER_PORT = 5000
DOWNLOAD_DIR = 'downloads'


def log(message):
    """Print timestamped log message"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [CLIENT] {message}")


def contact_index_server(filename):
    """Contact Index Server to get Content Server address for a file"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect((INDEX_SERVER_HOST, INDEX_SERVER_PORT))
        log(f"Connected to Index Server at {INDEX_SERVER_HOST}:{INDEX_SERVER_PORT}")
        
        # Send HELLO
        sock.sendall(b"HELLO\n")
        response = sock.recv(1024).decode('utf-8').strip()
        log(f"Index Server says: {response}")
        
        # Request file
        sock.sendall(f"GET {filename}\n".encode('utf-8'))
        response = sock.recv(1024).decode('utf-8').strip()
        log(f"Index Server response: {response}")
        
        sock.close()
        
        if response.startswith("SERVER"):
            parts = response.split()
            if len(parts) >= 5:
                _, ip, port, server_id, file_size = parts[:5]
                return ip, int(port), server_id, int(file_size)
        elif response.startswith("ERROR"):
            log(f"Error: {response}")
            return None
            
        return None
        
    except Exception as e:
        log(f"Failed to contact Index Server: {e}")
        return None


def download_from_content_server(ip, port, server_id, filename, expected_size):
    """Download file from Content Server"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(30)
        sock.connect((ip, port))
        log(f"Connected to Content Server {server_id} at {ip}:{port}")
        
        # Request file
        sock.sendall(f"GET {filename}\n".encode('utf-8'))
        
        # Read response header
        header = b""
        while b"\n" not in header:
            chunk = sock.recv(1)
            if not chunk:
                break
            header += chunk
            
        response = header.decode('utf-8').strip()
        log(f"Content Server response: {response}")
        
        if response.startswith("OK"):
            parts = response.split()
            file_size = int(parts[1]) if len(parts) > 1 else expected_size
            
            # Create download directory
            if not os.path.exists(DOWNLOAD_DIR):
                os.makedirs(DOWNLOAD_DIR)
                
            # Download file
            output_path = os.path.join(DOWNLOAD_DIR, filename)
            received = 0
            
            with open(output_path, 'wb') as f:
                while received < file_size:
                    chunk = sock.recv(min(4096, file_size - received))
                    if not chunk:
                        break
                    f.write(chunk)
                    received += len(chunk)
                    
                    # Progress indicator
                    progress = (received / file_size) * 100
                    print(f"\rDownloading: {progress:.1f}% ({received}/{file_size} bytes)", end="")
                    
            print()  # New line after progress
            
            sock.close()
            
            if received == file_size:
                log(f"Successfully downloaded: {output_path} ({received} bytes)")
                return True
            else:
                log(f"Warning: Downloaded {received} bytes, expected {file_size} bytes")
                return False
                
        elif response.startswith("ERROR"):
            log(f"Content Server error: {response}")
            sock.close()
            return False
            
    except Exception as e:
        log(f"Failed to download from Content Server: {e}")
        return False


def list_available_files():
    """List all available files from Index Server"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect((INDEX_SERVER_HOST, INDEX_SERVER_PORT))
        
        sock.sendall(b"LIST_FILES\n")
        
        response = ""
        while "END" not in response:
            data = sock.recv(1024)
            if not data:
                break
            response += data.decode('utf-8')
            
        sock.close()
        
        print("\nAvailable files:")
        print("-" * 40)
        for line in response.strip().split('\n'):
            if line.startswith("FILE"):
                parts = line.split()
                if len(parts) >= 3:
                    print(f"  {parts[1]} ({parts[2]} bytes)")
        print("-" * 40)
        
    except Exception as e:
        log(f"Failed to list files: {e}")


def list_servers():
    """List all servers from Index Server"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect((INDEX_SERVER_HOST, INDEX_SERVER_PORT))
        
        sock.sendall(b"LIST_SERVERS\n")
        
        response = ""
        while "END" not in response:
            data = sock.recv(1024)
            if not data:
                break
            response += data.decode('utf-8')
            
        sock.close()
        
        print("\nRegistered servers:")
        print("-" * 60)
        for line in response.strip().split('\n'):
            if line.startswith("SERVER"):
                parts = line.split()
                if len(parts) >= 6:
                    print(f"  {parts[1]}: {parts[2]}:{parts[3]} (load={parts[4]}, status={parts[5]})")
        print("-" * 60)
        
    except Exception as e:
        log(f"Failed to list servers: {e}")


def download_file(filename):
    """Download a file from the CDN"""
    log(f"Requesting file: {filename}")
    
    # Step 1: Contact Index Server
    result = contact_index_server(filename)
    
    if result is None:
        log("Could not locate file")
        return False
        
    ip, port, server_id, file_size = result
    log(f"File located on server {server_id} ({ip}:{port}), size: {file_size} bytes")
    
    # Step 2: Download from Content Server
    success = download_from_content_server(ip, port, server_id, filename, file_size)
    
    return success


def interactive_mode():
    """Interactive mode for downloading files"""
    print("\n" + "=" * 50)
    print("  Micro-CDN Client - Interactive Mode")
    print("=" * 50)
    print("\nCommands:")
    print("  get <filename>  - Download a file")
    print("  list            - List available files")
    print("  servers         - List registered servers")
    print("  quit            - Exit")
    print()
    
    while True:
        try:
            command = input("CDN> ").strip()
            
            if not command:
                continue
                
            parts = command.split()
            cmd = parts[0].lower()
            
            if cmd == "quit" or cmd == "exit":
                print("Goodbye!")
                break
            elif cmd == "get" and len(parts) >= 2:
                download_file(parts[1])
            elif cmd == "list":
                list_available_files()
            elif cmd == "servers":
                list_servers()
            elif cmd == "help":
                print("Commands: get <filename>, list, servers, quit")
            else:
                print("Unknown command. Type 'help' for available commands.")
                
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except EOFError:
            break


def main():
    parser = argparse.ArgumentParser(description='Client for Micro-CDN')
    parser.add_argument('filename', nargs='?', help='File to download')
    parser.add_argument('--index-host', type=str, default='localhost', help='Index Server host')
    parser.add_argument('--index-port', type=int, default=5000, help='Index Server port')
    parser.add_argument('--output-dir', type=str, default='downloads', help='Download directory')
    parser.add_argument('-i', '--interactive', action='store_true', help='Interactive mode')
    parser.add_argument('--list', action='store_true', help='List available files')
    parser.add_argument('--servers', action='store_true', help='List registered servers')
    
    args = parser.parse_args()
    
    global INDEX_SERVER_HOST, INDEX_SERVER_PORT, DOWNLOAD_DIR
    INDEX_SERVER_HOST = args.index_host
    INDEX_SERVER_PORT = args.index_port
    DOWNLOAD_DIR = args.output_dir
    
    if args.list:
        list_available_files()
    elif args.servers:
        list_servers()
    elif args.interactive or args.filename is None:
        interactive_mode()
    else:
        success = download_file(args.filename)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
