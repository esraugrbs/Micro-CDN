#!/usr/bin/env python3
"""
Content Server
- Hosts files and serves them to clients via TCP
- Sends periodic heartbeats to Monitor via UDP
- Registers with Index Server
"""

import socket
import threading
import time
import os
import sys
import argparse
from datetime import datetime

# Default configuration
DEFAULT_TCP_PORT = 7001
DEFAULT_UDP_PORT = 7002
INDEX_SERVER_HOST = 'localhost'
INDEX_SERVER_PORT = 5000
MONITOR_HOST = 'localhost'
MONITOR_UDP_PORT = 6000
HEARTBEAT_INTERVAL = 3  # seconds

# Global state
active_connections = 0
connections_lock = threading.Lock()


def log(server_id, message):
    """Print timestamped log message"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [CONTENT-{server_id}] {message}")


class ContentServer:
    def __init__(self, server_id, tcp_port, udp_port, files_dir):
        self.server_id = server_id
        self.tcp_port = tcp_port
        self.udp_port = udp_port
        self.files_dir = files_dir
        self.files = {}  # file_name -> file_size
        self.active_clients = 0
        self.clients_lock = threading.Lock()
        self.running = True
        
    def log(self, message):
        log(self.server_id, message)
        
    def scan_files(self):
        """Scan directory for files to serve"""
        if not os.path.exists(self.files_dir):
            os.makedirs(self.files_dir)
            self.log(f"Created files directory: {self.files_dir}")
            
        for filename in os.listdir(self.files_dir):
            filepath = os.path.join(self.files_dir, filename)
            if os.path.isfile(filepath):
                file_size = os.path.getsize(filepath)
                self.files[filename] = file_size
                self.log(f"Found file: {filename} ({file_size} bytes)")
                
        if not self.files:
            self.log("No files found in directory. Creating sample files...")
            self.create_sample_files()
            
    def create_sample_files(self):
        """Create sample files for testing"""
        samples = [
            (f"sample_{self.server_id}_1.txt", b"Hello from Content Server " + self.server_id.encode() + b"!\nThis is sample file 1.\n"),
            (f"sample_{self.server_id}_2.txt", b"Sample file 2 content from " + self.server_id.encode() + b"\n" * 100),
            (f"shared_file.txt", b"This file might be on multiple servers.\n" * 50),
        ]
        
        for filename, content in samples:
            filepath = os.path.join(self.files_dir, filename)
            with open(filepath, 'wb') as f:
                f.write(content)
            self.files[filename] = len(content)
            self.log(f"Created sample file: {filename} ({len(content)} bytes)")
            
    def register_with_index_server(self):
        """Register this server and its files with the Index Server"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((INDEX_SERVER_HOST, INDEX_SERVER_PORT))
            
            # Send registration
            reg_msg = f"REGISTER {self.server_id} {self.tcp_port} {self.udp_port}\n"
            sock.sendall(reg_msg.encode('utf-8'))
            response = sock.recv(1024).decode('utf-8').strip()
            self.log(f"Registration response: {response}")
            
            # Send file list
            for filename, size in self.files.items():
                msg = f"ADD_FILE {self.server_id} {filename} {size}\n"
                sock.sendall(msg.encode('utf-8'))
                
            sock.sendall(b"DONE_FILES\n")
            response = sock.recv(1024).decode('utf-8').strip()
            self.log(f"Files registration response: {response}")
            
            sock.close()
            return True
        except Exception as e:
            self.log(f"Failed to register with Index Server: {e}")
            return False
            
    def send_heartbeat(self):
        """Send heartbeat to Monitor via UDP"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        while self.running:
            try:
                with self.clients_lock:
                    load = self.active_clients
                    
                message = f"HEARTBEAT {self.server_id} localhost {self.tcp_port} {load} {len(self.files)}"
                sock.sendto(message.encode('utf-8'), (MONITOR_HOST, MONITOR_UDP_PORT))
                self.log(f"Sent heartbeat: load={load}, files={len(self.files)}")
            except Exception as e:
                self.log(f"Failed to send heartbeat: {e}")
                
            time.sleep(HEARTBEAT_INTERVAL)
            
        sock.close()
        
    def handle_client(self, conn, addr):
        """Handle client file download request"""
        with self.clients_lock:
            self.active_clients += 1
            
        self.log(f"Client connected from {addr}")
        
        try:
            while True:
                data = conn.recv(1024)
                if not data:
                    break
                    
                message = data.decode('utf-8').strip()
                self.log(f"Client request: {message}")
                
                if message.startswith("GET"):
                    parts = message.split()
                    if len(parts) >= 2:
                        filename = parts[1]
                        
                        if filename in self.files:
                            filepath = os.path.join(self.files_dir, filename)
                            file_size = self.files[filename]
                            
                            # Send OK response
                            conn.sendall(f"OK {file_size}\n".encode('utf-8'))
                            
                            # Send file content
                            with open(filepath, 'rb') as f:
                                while True:
                                    chunk = f.read(4096)
                                    if not chunk:
                                        break
                                    conn.sendall(chunk)
                                    
                            self.log(f"Sent file: {filename} ({file_size} bytes)")
                        else:
                            conn.sendall(b"ERROR FILE_NOT_FOUND\n")
                            self.log(f"File not found: {filename}")
                    else:
                        conn.sendall(b"ERROR INVALID_FORMAT\n")
                else:
                    conn.sendall(b"ERROR UNKNOWN_COMMAND\n")
                    
                # Close connection after file transfer
                break
                
        except Exception as e:
            self.log(f"Error handling client: {e}")
        finally:
            conn.close()
            with self.clients_lock:
                self.active_clients -= 1
            self.log(f"Client disconnected from {addr}")
            
    def start_tcp_server(self):
        """Start TCP server for file downloads"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('0.0.0.0', self.tcp_port))
        sock.listen(10)
        self.log(f"TCP server started on port {self.tcp_port}")
        
        while self.running:
            try:
                sock.settimeout(1)
                conn, addr = sock.accept()
                client_thread = threading.Thread(target=self.handle_client, args=(conn, addr))
                client_thread.daemon = True
                client_thread.start()
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    self.log(f"Error accepting connection: {e}")
                    
        sock.close()
        
    def start(self):
        """Start the Content Server"""
        self.log(f"Starting Content Server {self.server_id}...")
        self.log(f"TCP Port: {self.tcp_port}, UDP Port: {self.udp_port}")
        self.log(f"Files directory: {self.files_dir}")
        
        # Scan for files
        self.scan_files()
        
        # Register with Index Server
        if not self.register_with_index_server():
            self.log("Warning: Could not register with Index Server")
            
        # Start heartbeat thread
        heartbeat_thread = threading.Thread(target=self.send_heartbeat)
        heartbeat_thread.daemon = True
        heartbeat_thread.start()
        
        # Start TCP server (blocking)
        self.start_tcp_server()


def main():
    parser = argparse.ArgumentParser(description='Content Server for Micro-CDN')
    parser.add_argument('--id', type=str, default='CS1', help='Server ID (default: CS1)')
    parser.add_argument('--tcp-port', type=int, default=DEFAULT_TCP_PORT, help='TCP port (default: 7001)')
    parser.add_argument('--udp-port', type=int, default=DEFAULT_UDP_PORT, help='UDP port (default: 7002)')
    parser.add_argument('--files-dir', type=str, default=None, help='Directory containing files to serve')
    
    args = parser.parse_args()
    
    # Set default files directory based on server ID
    if args.files_dir is None:
        args.files_dir = f"files_{args.id}"
        
    server = ContentServer(args.id, args.tcp_port, args.udp_port, args.files_dir)
    
    try:
        server.start()
    except KeyboardInterrupt:
        server.running = False
        server.log("Shutting down...")


if __name__ == "__main__":
    main()
