#!/usr/bin/env python3
"""
Monitor / Health Server
- UDP Interface: Receives heartbeats from Content Servers (port 6000)
- TCP Interface: Provides server status to Index Server (port 6001)
- Detects failed Content Servers and notifies Index Server
"""

import socket
import threading
import time
import sys
from datetime import datetime

# Configuration
UDP_PORT = 6000
TCP_PORT = 6001
HEARTBEAT_TIMEOUT = 8  # seconds - server considered dead if no heartbeat

# Data structure to store server information
# server_id -> {ip, tcp_port, last_seen, load, num_files, status}
servers = {}
servers_lock = threading.Lock()

# Index Server connection for failure notifications
index_server_addr = None
index_server_lock = threading.Lock()


def log(message):
    """Print timestamped log message"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [MONITOR] {message}")


def udp_heartbeat_listener():
    """Listen for UDP heartbeats from Content Servers"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('0.0.0.0', UDP_PORT))
    log(f"UDP heartbeat listener started on port {UDP_PORT}")
    
    while True:
        try:
            data, addr = sock.recvfrom(1024)
            message = data.decode('utf-8').strip()
            
            if message.startswith("HEARTBEAT"):
                parts = message.split()
                if len(parts) >= 6:
                    _, server_id, ip, tcp_port, load, num_files = parts[:6]
                    
                    with servers_lock:
                        was_dead = server_id in servers and servers[server_id]['status'] == 'dead'
                        servers[server_id] = {
                            'ip': ip,
                            'tcp_port': int(tcp_port),
                            'last_seen': time.time(),
                            'load': int(load),
                            'num_files': int(num_files),
                            'status': 'alive'
                        }
                        
                        if was_dead:
                            log(f"Server {server_id} came back online!")
                        else:
                            log(f"Heartbeat from {server_id}: load={load}, files={num_files}")
        except Exception as e:
            log(f"Error processing heartbeat: {e}")


def check_server_health():
    """Periodically check if servers have timed out"""
    while True:
        time.sleep(2)  # Check every 2 seconds
        current_time = time.time()
        
        with servers_lock:
            for server_id, info in servers.items():
                if info['status'] == 'alive':
                    time_since_heartbeat = current_time - info['last_seen']
                    if time_since_heartbeat > HEARTBEAT_TIMEOUT:
                        info['status'] = 'dead'
                        log(f"Server {server_id} marked as DEAD (no heartbeat for {time_since_heartbeat:.1f}s)")
                        notify_index_server_failure(server_id)


def notify_index_server_failure(server_id):
    """Notify Index Server about a server failure"""
    with index_server_lock:
        if index_server_addr:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                sock.connect(index_server_addr)
                timestamp = int(time.time())
                message = f"SERVER_DOWN {server_id} {timestamp}\n"
                sock.sendall(message.encode('utf-8'))
                sock.close()
                log(f"Notified Index Server about {server_id} failure")
            except Exception as e:
                log(f"Failed to notify Index Server: {e}")


def handle_tcp_client(conn, addr):
    """Handle TCP connections from Index Server"""
    global index_server_addr
    
    log(f"TCP connection from {addr}")
    
    try:
        while True:
            data = conn.recv(1024)
            if not data:
                break
            
            message = data.decode('utf-8').strip()
            log(f"Received: {message}")
            
            if message == "LIST_SERVERS":
                with servers_lock:
                    response = ""
                    for server_id, info in servers.items():
                        response += f"SERVER {server_id} {info['ip']} {info['tcp_port']} {info['load']} {info['status']}\n"
                    response += "END\n"
                conn.sendall(response.encode('utf-8'))
                
            elif message.startswith("REGISTER_INDEX"):
                # Index Server registers itself for failure notifications
                parts = message.split()
                if len(parts) >= 3:
                    index_ip = parts[1]
                    index_port = int(parts[2])
                    with index_server_lock:
                        index_server_addr = (index_ip, index_port)
                    conn.sendall(b"OK INDEX_REGISTERED\n")
                    log(f"Index Server registered at {index_ip}:{index_port}")
                else:
                    conn.sendall(b"ERROR INVALID_FORMAT\n")
                    
            elif message == "PING":
                conn.sendall(b"PONG\n")
                
            else:
                conn.sendall(b"ERROR UNKNOWN_COMMAND\n")
                
    except Exception as e:
        log(f"Error handling TCP client: {e}")
    finally:
        conn.close()
        log(f"TCP connection from {addr} closed")


def tcp_server():
    """TCP server for Index Server queries"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('0.0.0.0', TCP_PORT))
    sock.listen(5)
    log(f"TCP server started on port {TCP_PORT}")
    
    while True:
        conn, addr = sock.accept()
        client_thread = threading.Thread(target=handle_tcp_client, args=(conn, addr))
        client_thread.daemon = True
        client_thread.start()


def main():
    log("Starting Monitor/Health Server...")
    log(f"UDP Port: {UDP_PORT}, TCP Port: {TCP_PORT}")
    log(f"Heartbeat timeout: {HEARTBEAT_TIMEOUT} seconds")
    
    # Start UDP heartbeat listener
    udp_thread = threading.Thread(target=udp_heartbeat_listener)
    udp_thread.daemon = True
    udp_thread.start()
    
    # Start health checker
    health_thread = threading.Thread(target=check_server_health)
    health_thread.daemon = True
    health_thread.start()
    
    # Start TCP server (main thread)
    tcp_server()


if __name__ == "__main__":
    main()
