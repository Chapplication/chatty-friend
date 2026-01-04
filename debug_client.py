#!/usr/bin/env python3
"""
Debug Log Client for Chatty Friend

Connects to the debug log server on a Raspberry Pi and displays
trace logs in real-time with optional filtering.

Usage:
    python debug_client.py <host> [--port PORT] [--filter COMPONENT]

Examples:
    python debug_client.py 192.168.1.100
    python debug_client.py 192.168.1.100 --filter mic
    python debug_client.py 192.168.1.100 --filter wake
    python debug_client.py 192.168.1.100 -p 9999 -f ws
"""

import argparse
import json
import socket
import sys
from datetime import datetime

# ANSI color codes for terminal output
COLORS = {
    "mic": "\033[36m",      # Cyan
    "vad": "\033[35m",      # Magenta
    "wake": "\033[33m",     # Yellow
    "ws": "\033[32m",       # Green
    "spkr": "\033[34m",     # Blue
    "main": "\033[37m",     # White
    "tool": "\033[95m",     # Light magenta
    "audio_out": "\033[96m", # Light cyan
    "error": "\033[31m",    # Red
}
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"


def colorize(component: str, text: str) -> str:
    """Apply color based on component."""
    color = COLORS.get(component, "\033[37m")
    return f"{color}{text}{RESET}"


def format_entry(entry: dict, use_color: bool = True) -> str:
    """Format a log entry for display."""
    ts = entry.get("ts", "")
    component = entry.get("c", "?")
    msg = entry.get("m", "")
    
    # Extract just time portion for readability
    try:
        dt = datetime.fromisoformat(ts)
        time_str = dt.strftime("%H:%M:%S.") + f"{dt.microsecond // 1000:03d}"
    except:
        time_str = ts
    
    if use_color:
        return f"{DIM}{time_str}{RESET} {colorize(component, f'[{component:8s}]')} {msg}"
    else:
        return f"{time_str} [{component:8s}] {msg}"


def main():
    parser = argparse.ArgumentParser(
        description="Connect to Chatty Friend debug log server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s 192.168.1.100              # Connect and stream all logs
  %(prog)s 192.168.1.100 -f mic       # Filter to mic component only
  %(prog)s 192.168.1.100 -f wake      # Filter to wake word events
  %(prog)s pi.local -p 9999           # Use hostname and custom port

Alternative (no dependencies):
  nc 192.168.1.100 9999 | grep '"c":"mic"'
"""
    )
    parser.add_argument("host", help="Pi hostname or IP address")
    parser.add_argument("-p", "--port", type=int, default=9999,
                        help="Debug server port (default: 9999)")
    parser.add_argument("-f", "--filter", dest="component_filter",
                        help="Filter by component (e.g., mic, ws, wake, spkr)")
    parser.add_argument("--no-color", action="store_true",
                        help="Disable colored output")
    parser.add_argument("-r", "--reconnect", action="store_true",
                        help="Auto-reconnect on disconnect")
    
    args = parser.parse_args()
    use_color = not args.no_color and sys.stdout.isatty()
    
    while True:
        try:
            connect_and_stream(args.host, args.port, args.component_filter, use_color)
        except KeyboardInterrupt:
            print("\n\nDisconnected.")
            break
        except ConnectionRefusedError:
            print(f"Connection refused. Is the debug server running on {args.host}:{args.port}?")
            if not args.reconnect:
                sys.exit(1)
            print("Reconnecting in 5 seconds...")
            import time
            time.sleep(5)
        except Exception as e:
            print(f"Error: {e}")
            if not args.reconnect:
                sys.exit(1)
            print("Reconnecting in 5 seconds...")
            import time
            time.sleep(5)


def connect_and_stream(host: str, port: int, component_filter: str, use_color: bool):
    """Connect to server and stream logs."""
    print(f"Connecting to {host}:{port}...")
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10.0)  # Connection timeout
    sock.connect((host, port))
    sock.settimeout(None)  # No timeout for streaming
    
    print(f"Connected! Streaming logs" + 
          (f" (filter: {component_filter})" if component_filter else "") + 
          "...\n")
    
    buffer = ""
    
    try:
        while True:
            data = sock.recv(4096)
            if not data:
                print("\nServer closed connection.")
                break
            
            buffer += data.decode('utf-8', errors='replace')
            
            # Process complete lines
            while '\n' in buffer:
                line, buffer = buffer.split('\n', 1)
                if not line.strip():
                    continue
                
                try:
                    entry = json.loads(line)
                    
                    # Check for error message
                    if "error" in entry:
                        print(f"Server error: {entry['error']}")
                        continue
                    
                    # Apply filter
                    if component_filter:
                        component = entry.get("c", "")
                        if component_filter.lower() not in component.lower():
                            continue
                    
                    print(format_entry(entry, use_color))
                    
                except json.JSONDecodeError:
                    # Not valid JSON, print raw
                    print(f"[raw] {line}")
                    
    finally:
        sock.close()


if __name__ == "__main__":
    main()
