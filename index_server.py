#!/usr/bin/env python3
"""
Index Server
- Tracks which content servers host which files
- Handles client queries to locate files
- Avoids dead servers based on Monitor information
"""

import socket
import threading
import time
import sys
from datetime import datetime

# Configuration
TCP_PORT = 5000
MONITOR_TCP_HOST = 'localhost'
MONITOR_TCP_PORT = 6001

# Data structures
# server_id -> {ip, tcp_port, udp_port, load, last_update, status}
content_servers = {}
# file_name -> [(server_id, file_size)]
file_index = {}

data_lock = threading.Lock()


def log(message):
    """Print timestamped log message"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [INDEX] {message}")


def get_server_health_from_monitor():
    """Query Monitor for current server status"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((MONITOR_TCP_HOST, MONITOR_TCP_PORT))
        sock.sendall(b"LIST_SERVERS\n")
        
        response = ""
        while True:
            data = sock.recv(1024)
            if not data:
                break
            response += data.decode('utf-8')
            if "END" in response:
                break
        
        sock.close()
        
        # Parse response
        with data_lock:
            for line in response.strip().split('\n'):
                if line.startswith("SERVER"):
                    parts = line.split()
                    if len(parts) >= 6:
                        _, server_id, ip, tcp_port, load, status = parts[:6]
                        if server_id in content_servers:
                            content_servers[server_id]['load'] = int(load)
                            content_servers[server_id]['status'] = status
                            
        return True
    except Exception as e:
        log(f"Could not reach Monitor: {e}")
        return False


def select_best_server(file_name):
    """Select the best server for a file based on load and availability"""
    with data_lock:
        if file_name not in file_index:
            return None, None
        
        candidates = []
        for server_id, file_size in file_index[file_name]:
            if server_id in content_servers:
                server = content_servers[server_id]
                if server['status'] == 'alive':
                    candidates.append((server_id, server, file_size))
        
        if not candidates:
            return None, None
        
        # Select server with lowest load
        candidates.sort(key=lambda x: x[1]['load'])
        best = candidates[0]
        return best[1], best[2]  # server info, file_size


def handle_content_server(conn, addr):
    """Handle registration from a Content Server"""
    log(f"Content Server connection from {addr}")
    
    try:
        server_id = None
        
        while True:
            data = conn.recv(4096)
            if not data:
                break
            
            lines = data.decode('utf-8').strip().split('\n')
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                log(f"Received: {line}")
                
                if line.startswith("REGISTER"):
                    parts = line.split()
                    if len(parts) >= 4:
                        _, server_id, tcp_port, udp_port = parts[:4]
                        with data_lock:
                            content_servers[server_id] = {
                                'ip': addr[0],
                                'tcp_port': int(tcp_port),
                                'udp_port': int(udp_port),
                                'load': 0,
                                'last_update': time.time(),
                                'status': 'alive'
                            }
                        conn.sendall(b"OK REGISTERED\n")
                        log(f"Registered Content Server: {server_id}")
                    else:
                        conn.sendall(b"ERROR INVALID_FORMAT\n")
                
                elif line.startswith("ADD_FILE"):
                    parts = line.split()
                    if len(parts) >= 4:
                        _, sid, file_name, file_size = parts[:4]
                        with data_lock:
                            if file_name not in file_index:
                                file_index[file_name] = []
                            # Avoid duplicates
                            existing = [(s, sz) for s, sz in file_index[file_name] if s == sid]
                            if not existing:
                                file_index[file_name].append((sid, int(file_size)))
                        log(f"Added file: {file_name} ({file_size} bytes) from {sid}")
                
                elif line == "DONE_FILES":
                    conn.sendall(b"OK FILES_ADDED\n")
                    log(f"File registration complete for {server_id}")
                    
                elif line.startswith("UPDATE_LOAD"):
                    parts = line.split()
                    if len(parts) >= 3:
                        _, sid, load = parts[:3]
                        with data_lock:
                            if sid in content_servers:
                                content_servers[sid]['load'] = int(load)
                                content_servers[sid]['last_update'] = time.time()
                        conn.sendall(b"OK\n")
                        
    except Exception as e:
        log(f"Error handling Content Server: {e}")
    finally:
        conn.close()
        log(f"Content Server connection from {addr} closed")


def handle_client(conn, addr):
    """Handle client queries"""
    log(f"Client connection from {addr}")
    
    try:
        while True:
            data = conn.recv(1024)
            if not data:
                break
            
            message = data.decode('utf-8').strip()
            log(f"Client request: {message}")
            
            if message == "HELLO":
                conn.sendall(b"WELCOME MICRO-CDN\n")
                
            elif message.startswith("GET"):
                parts = message.split()
                if len(parts) >= 2:
                    file_name = parts[1]
                    
                    # Get latest health info
                    get_server_health_from_monitor()
                    
                    server, file_size = select_best_server(file_name)
                    
                    if server:
                        response = f"SERVER {server['ip']} {server['tcp_port']} {server.get('server_id', 'unknown')} {file_size}\n"
                        # Include server_id in response
                        for sid, info in content_servers.items():
                            if info == server:
                                response = f"SERVER {server['ip']} {server['tcp_port']} {sid} {file_size}\n"
                                break
                        conn.sendall(response.encode('utf-8'))
                        log(f"Directed client to server at {server['ip']}:{server['tcp_port']}")
                    else:
                        conn.sendall(b"ERROR FILE_NOT_FOUND\n")
                        log(f"File not found: {file_name}")
                else:
                    conn.sendall(b"ERROR INVALID_FORMAT\n")
                    
            elif message == "LIST_FILES":
                # Extra command to list available files
                with data_lock:
                    response = ""
                    for file_name, servers_list in file_index.items():
                        for sid, size in servers_list:
                            if sid in content_servers and content_servers[sid]['status'] == 'alive':
                                response += f"FILE {file_name} {size}\n"
                                break
                    response += "END\n"
                conn.sendall(response.encode('utf-8'))
                
            elif message == "LIST_SERVERS":
                # Debug command
                with data_lock:
                    response = ""
                    for server_id, info in content_servers.items():
                        response += f"SERVER {server_id} {info['ip']} {info['tcp_port']} {info['load']} {info['status']}\n"
                    response += "END\n"
                conn.sendall(response.encode('utf-8'))
                    
            else:
                conn.sendall(b"ERROR UNKNOWN_COMMAND\n")
                
    except Exception as e:
        log(f"Error handling client: {e}")
    finally:
        conn.close()
        log(f"Client connection from {addr} closed")


def handle_monitor_notification(conn, addr):
    """Handle notifications from Monitor Server about failures"""
    try:
        data = conn.recv(1024)
        if data:
            message = data.decode('utf-8').strip()
            log(f"Monitor notification: {message}")
            
            if message.startswith("SERVER_DOWN"):
                parts = message.split()
                if len(parts) >= 2:
                    server_id = parts[1]
                    with data_lock:
                        if server_id in content_servers:
                            content_servers[server_id]['status'] = 'dead'
                            log(f"Marked server {server_id} as DEAD based on Monitor notification")
    except Exception as e:
        log(f"Error handling monitor notification: {e}")
    finally:
        conn.close()


def notification_listener():
    """Listen for failure notifications from Monitor"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('0.0.0.0', TCP_PORT + 1))  # Listen on 5001 for notifications
    sock.listen(5)
    log(f"Notification listener started on port {TCP_PORT + 1}")
    
    # Register with Monitor
    try:
        monitor_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        monitor_sock.connect((MONITOR_TCP_HOST, MONITOR_TCP_PORT))
        monitor_sock.sendall(f"REGISTER_INDEX localhost {TCP_PORT + 1}\n".encode('utf-8'))
        response = monitor_sock.recv(1024)
        log(f"Monitor registration response: {response.decode('utf-8').strip()}")
        monitor_sock.close()
    except Exception as e:
        log(f"Could not register with Monitor: {e}")
    
    while True:
        conn, addr = sock.accept()
        handle_monitor_notification(conn, addr)


def main():
    log("Starting Index Server...")
    log(f"TCP Port: {TCP_PORT}")
    
    # Start notification listener
    notif_thread = threading.Thread(target=notification_listener)
    notif_thread.daemon = True
    notif_thread.start()
    
    # Main TCP server
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('0.0.0.0', TCP_PORT))
    sock.listen(10)
    log(f"TCP server started on port {TCP_PORT}")
    
    while True:
        conn, addr = sock.accept()
        
        # Peek at first message to determine if it's a Content Server or Client
        conn.settimeout(5)
        try:
            data = conn.recv(1024, socket.MSG_PEEK)
            message = data.decode('utf-8').strip()
            
            if message.startswith("REGISTER"):
                # Content Server registration
                client_thread = threading.Thread(target=handle_content_server, args=(conn, addr))
            else:
                # Client query
                client_thread = threading.Thread(target=handle_client, args=(conn, addr))
            
            conn.settimeout(None)
            client_thread.daemon = True
            client_thread.start()
        except Exception as e:
            log(f"Error accepting connection: {e}")
            conn.close()


if __name__ == "__main__":
    main()
