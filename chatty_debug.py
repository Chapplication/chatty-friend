# Chatty Debug
# Finley 2025
#
# Lightweight TCP-based debug log server for real-time monitoring.
# FIFO buffer of last 1000 entries, streams to connected clients.
#

import asyncio
import json
from collections import deque
from datetime import datetime
from typing import Optional

# Global server instance
_server: Optional['DebugLogServer'] = None


class DebugLogServer:
    """
    TCP server that buffers trace logs and streams them to connected clients.
    
    Pi Safety Measures:
    - Non-blocking trace() with overflow protection
    - Bounded queue and buffer to prevent memory growth
    - Max client limit to reduce CPU/network overhead
    - Graceful shutdown with timeout
    """
    
    MAX_CLIENTS = 3
    QUEUE_SIZE = 100
    BUFFER_SIZE = 1000
    SHUTDOWN_TIMEOUT = 2.0
    
    def __init__(self, port: int = 9999):
        self._port = port
        self._buffer: deque = deque(maxlen=self.BUFFER_SIZE)  # FIFO: append right, iterate left-to-right
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=self.QUEUE_SIZE)
        self._clients: set = set()
        self._shutdown: asyncio.Event = asyncio.Event()
        self._server: Optional[asyncio.Server] = None
        self._processor_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start the debug server and log processor."""
        try:
            self._server = await asyncio.start_server(
                self._handle_client,
                '0.0.0.0',
                self._port
            )
            self._processor_task = asyncio.create_task(self._process_queue())
            print(f"🔍 Debug server listening on port {self._port}")
        except Exception as e:
            print(f"⚠️ Debug server failed to start: {e}")
    
    async def stop(self):
        """Gracefully shutdown the server."""
        self._shutdown.set()
        
        # Close all client connections
        for writer in list(self._clients):
            try:
                writer.close()
                await asyncio.wait_for(writer.wait_closed(), timeout=0.5)
            except:
                pass
        self._clients.clear()
        
        # Stop the processor task
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await asyncio.wait_for(self._processor_task, timeout=self.SHUTDOWN_TIMEOUT)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
        
        # Close the server
        if self._server:
            self._server.close()
            try:
                await asyncio.wait_for(self._server.wait_closed(), timeout=self.SHUTDOWN_TIMEOUT)
            except asyncio.TimeoutError:
                pass
        
        print("🔍 Debug server stopped")
    
    async def _process_queue(self):
        """Process incoming trace entries from queue to buffer and clients."""
        while not self._shutdown.is_set():
            try:
                # Wait for entry with timeout to check shutdown flag
                try:
                    entry = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                
                # Add to buffer (FIFO)
                self._buffer.append(entry)
                
                # Send to all connected clients
                line = json.dumps(entry) + '\n'
                line_bytes = line.encode('utf-8')
                
                dead_clients = set()
                for writer in self._clients:
                    try:
                        writer.write(line_bytes)
                        await writer.drain()
                    except:
                        dead_clients.add(writer)
                
                # Remove dead clients
                self._clients -= dead_clients
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                # Log processing should never crash
                pass
    
    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle a new client connection."""
        # Check client limit
        if len(self._clients) >= self.MAX_CLIENTS:
            try:
                writer.write(b'{"error": "max clients reached"}\n')
                await writer.drain()
                writer.close()
                await writer.wait_closed()
            except:
                pass
            return
        
        peer = writer.get_extra_info('peername')
        print(f"🔍 Debug client connected: {peer}")
        
        try:
            # Send buffered logs in FIFO order (oldest first)
            for entry in self._buffer:
                line = json.dumps(entry) + '\n'
                writer.write(line.encode('utf-8'))
            await writer.drain()
            
            # Add to active clients for streaming
            self._clients.add(writer)
            
            # Keep connection alive until client disconnects or shutdown
            while not self._shutdown.is_set():
                try:
                    # Check if client is still connected by reading
                    data = await asyncio.wait_for(reader.read(1), timeout=5.0)
                    if not data:
                        break  # Client disconnected
                except asyncio.TimeoutError:
                    # Just a timeout, client still connected
                    continue
                except:
                    break
                    
        except Exception as e:
            pass
        finally:
            self._clients.discard(writer)
            try:
                writer.close()
                await writer.wait_closed()
            except:
                pass
            print(f"🔍 Debug client disconnected: {peer}")
    
    def post(self, component: str, msg: str):
        """
        Post a trace entry to the queue (non-blocking).
        Silently drops if queue is full.
        """
        if self._shutdown.is_set():
            return
        
        entry = {
            "ts": datetime.now().isoformat(timespec='milliseconds'),
            "c": component,
            "m": msg
        }
        
        try:
            self._queue.put_nowait(entry)
        except asyncio.QueueFull:
            # Drop log rather than block - audio pipeline > logging
            pass


async def start_debug_server(port: int = 9999) -> bool:
    """
    Start the global debug log server.
    
    Args:
        port: TCP port to listen on (default 9999)
    
    Returns:
        True if server started, False otherwise
    """
    global _server
    
    if _server is not None:
        return True  # Already running
    
    try:
        _server = DebugLogServer(port=port)
        await _server.start()
        return True
    except Exception as e:
        print(f"⚠️ Failed to start debug server: {e}")
        _server = None
        return False


async def stop_debug_server():
    """Stop the global debug log server."""
    global _server
    
    if _server is not None:
        await _server.stop()
        _server = None


def trace(component: str, msg: str):
    """
    Fire-and-forget trace function.
    
    Never blocks, never raises. Safe to call from anywhere.
    If no server is running or queue is full, the log is silently dropped.
    
    Args:
        component: Short identifier (e.g., "mic", "ws", "spkr")
        msg: Log message
    
    Example:
        trace("mic", "wake word detected")
        trace("ws", f"session created id={session_id}")
    """
    try:
        if _server is not None:
            _server.post(component, msg)
    except:
        pass  # Never raise - audio pipeline > logging
