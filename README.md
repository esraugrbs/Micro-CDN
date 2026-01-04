# Micro-CDN: File Distribution System

A simplified Content Delivery Network (CDN) implementation that distributes files to clients through multiple content servers, coordinated by an index server and monitored by a health server.

## System Architecture

The system consists of four main components:

1. **Monitor/Health Server** (`monitor_server.py`) - Tracks content server health via UDP heartbeats
2. **Index Server** (`index_server.py`) - Coordinates file locations and client requests
3. **Content Server** (`content_server.py`) - Hosts and serves files to clients
4. **Client** (`client.py`) - Downloads files from the CDN

```
                    Monitor / Health Server
                      (UDP 6000 + TCP 6001)
                              |
            heartbeats (UDP)  |  status queries (TCP)
                    +---------+---------+
                    |                   |
             Content Server 1    Content Server 2
              (TCP 7001)          (TCP 7101)
                    |                   |
                    +-------------------+
                              |
                      Index Server
                       (TCP 5000)
                              |
          +-------------------+-------------------+
          |                   |                   |
       Client 1            Client 2            Client 3
```

## Requirements

- Python 3.6+
- No external dependencies (uses only standard library)

## Quick Start

### Step 1: Start the Monitor Server

```bash
python monitor_server.py
```

This starts the health monitoring server on:
- UDP port 6000 (heartbeat reception)
- TCP port 6001 (status queries)

### Step 2: Start the Index Server

```bash
python index_server.py
```

This starts the index server on TCP port 5000.

### Step 3: Start Content Servers

Start at least two content servers with different IDs and ports:

**Content Server 1:**
```bash
python content_server.py --id CS1 --tcp-port 7001 --udp-port 7002 --files-dir files_CS1
```

**Content Server 2:**
```bash
python content_server.py --id CS2 --tcp-port 7101 --udp-port 7102 --files-dir files_CS2
```

### Step 4: Run the Client

**Interactive mode:**
```bash
python client.py -i
```

**Download a specific file:**
```bash
python client.py shared_document.txt
```

**List available files:**
```bash
python client.py --list
```

**List registered servers:**
```bash
python client.py --servers
```

## Port Configuration

| Component | Protocol | Default Port | Purpose |
|-----------|----------|--------------|---------|
| Monitor Server | UDP | 6000 | Heartbeat reception |
| Monitor Server | TCP | 6001 | Status queries |
| Index Server | TCP | 5000 | Client queries, server registration |
| Index Server | TCP | 5001 | Failure notifications |
| Content Server 1 | TCP | 7001 | File downloads |
| Content Server 1 | UDP | 7002 | Heartbeats |
| Content Server 2 | TCP | 7101 | File downloads |
| Content Server 2 | UDP | 7102 | Heartbeats |

## Protocol Specification

### Index Server Protocol (TCP)

#### Content Server Registration
```
REGISTER <server_id> <tcp_port> <udp_port>
-> OK REGISTERED

ADD_FILE <server_id> <file_name> <file_size>
...
DONE_FILES
-> OK FILES_ADDED
```

#### Client File Request
```
HELLO
-> WELCOME MICRO-CDN

GET <file_name>
-> SERVER <ip> <tcp_port> <server_id> <file_size>
   OR
-> ERROR FILE_NOT_FOUND
```

#### Additional Commands
```
LIST_FILES
-> FILE <file_name> <file_size>
   ...
   END

LIST_SERVERS
-> SERVER <server_id> <ip> <tcp_port> <load> <status>
   ...
   END
```

### Content Server Protocol (TCP)

#### File Download
```
GET <file_name>
-> OK <file_size>
   <file_bytes>
   OR
-> ERROR FILE_NOT_FOUND
```

### Monitor Protocol

#### UDP Heartbeat (Content Server → Monitor)
```
HEARTBEAT <server_id> <ip> <tcp_port> <load> <num_files>
```

#### TCP Status Query (Index Server → Monitor)
```
LIST_SERVERS
-> SERVER <server_id> <ip> <tcp_port> <load> <status>
   ...
   END

REGISTER_INDEX <ip> <port>
-> OK INDEX_REGISTERED
```

#### TCP Failure Notification (Monitor → Index Server)
```
SERVER_DOWN <server_id> <timestamp>
```

## Error Handling

- **Invalid messages**: Servers respond with `ERROR UNKNOWN_COMMAND` or `ERROR INVALID_FORMAT`
- **File not found**: Returns `ERROR FILE_NOT_FOUND`
- **Server failure**: Monitor detects missing heartbeats (8-second timeout) and notifies Index Server
- **Connection errors**: Gracefully handled with logging

## Testing Scenario

### Test 1: Basic File Distribution

1. Start all servers (Monitor, Index, CS1, CS2)
2. Run client to list available files
3. Download a file from CS1
4. Download a shared file (should be served by least-loaded server)

### Test 2: Server Failure Detection

1. Start all servers
2. Download a file successfully
3. Kill Content Server 1 (Ctrl+C)
4. Wait 8 seconds for timeout
5. Verify Monitor logs show server as DEAD
6. Try to download a file only on CS1 (should fail or use alternative)
7. Download shared file (should be served by CS2)

### Test 3: Concurrent Downloads

1. Start all servers
2. Run multiple clients simultaneously
3. Verify load balancing (check Monitor logs for load values)

## Sample Console Output

### Monitor Server
```
[2025-01-01 12:00:00] [MONITOR] Starting Monitor/Health Server...
[2025-01-01 12:00:00] [MONITOR] UDP heartbeat listener started on port 6000
[2025-01-01 12:00:00] [MONITOR] TCP server started on port 6001
[2025-01-01 12:00:05] [MONITOR] Heartbeat from CS1: load=0, files=3
[2025-01-01 12:00:05] [MONITOR] Heartbeat from CS2: load=0, files=2
[2025-01-01 12:00:15] [MONITOR] Server CS1 marked as DEAD (no heartbeat for 10.0s)
```

### Index Server
```
[2025-01-01 12:00:01] [INDEX] Starting Index Server...
[2025-01-01 12:00:02] [INDEX] Registered Content Server: CS1
[2025-01-01 12:00:02] [INDEX] Added file: sample_cs1.txt (500 bytes) from CS1
[2025-01-01 12:00:03] [INDEX] Client request: GET shared_document.txt
[2025-01-01 12:00:03] [INDEX] Directed client to server at localhost:7001
```

### Content Server
```
[2025-01-01 12:00:01] [CONTENT-CS1] Starting Content Server CS1...
[2025-01-01 12:00:01] [CONTENT-CS1] Found file: sample_cs1.txt (500 bytes)
[2025-01-01 12:00:01] [CONTENT-CS1] TCP server started on port 7001
[2025-01-01 12:00:05] [CONTENT-CS1] Sent heartbeat: load=0, files=3
[2025-01-01 12:00:10] [CONTENT-CS1] Client connected from ('127.0.0.1', 52431)
[2025-01-01 12:00:10] [CONTENT-CS1] Sent file: shared_document.txt (600 bytes)
```

### Client
```
[2025-01-01 12:00:10] [CLIENT] Requesting file: shared_document.txt
[2025-01-01 12:00:10] [CLIENT] Connected to Index Server at localhost:5000
[2025-01-01 12:00:10] [CLIENT] Index Server says: WELCOME MICRO-CDN
[2025-01-01 12:00:10] [CLIENT] File located on server CS1 (localhost:7001), size: 600 bytes
[2025-01-01 12:00:10] [CLIENT] Connected to Content Server CS1 at localhost:7001
Downloading: 100.0% (600/600 bytes)
[2025-01-01 12:00:10] [CLIENT] Successfully downloaded: downloads/shared_document.txt (600 bytes)
```

## File Structure

```
nw/
├── monitor_server.py    # Monitor/Health Server
├── index_server.py      # Index Server
├── content_server.py    # Content Server
├── client.py            # Client Program
├── README.md            # This file
├── files_CS1/           # Files for Content Server 1
│   ├── sample_cs1.txt
│   ├── shared_document.txt
│   └── large_file.bin
├── files_CS2/           # Files for Content Server 2
│   ├── sample_cs2.txt
│   └── shared_document.txt
└── downloads/           # Downloaded files (created by client)
```

## Configuration

### Monitor Server
- `UDP_PORT`: UDP port for heartbeats (default: 6000)
- `TCP_PORT`: TCP port for queries (default: 6001)
- `HEARTBEAT_TIMEOUT`: Seconds before marking server dead (default: 8)

### Index Server
- `TCP_PORT`: TCP port for clients (default: 5000)
- `MONITOR_TCP_HOST`: Monitor server host (default: localhost)
- `MONITOR_TCP_PORT`: Monitor server TCP port (default: 6001)

### Content Server
Command-line arguments:
- `--id`: Server ID (default: CS1)
- `--tcp-port`: TCP port (default: 7001)
- `--udp-port`: UDP port (default: 7002)
- `--files-dir`: Directory containing files (default: files_<id>)

### Client
Command-line arguments:
- `--index-host`: Index Server host (default: localhost)
- `--index-port`: Index Server port (default: 5000)
- `--output-dir`: Download directory (default: downloads)
- `-i, --interactive`: Interactive mode


