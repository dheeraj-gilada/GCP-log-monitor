"""
WebSocket endpoints for real-time monitoring and log streaming.
Handles live updates for dashboard and alert notifications.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from typing import List, Dict, Set
import json
import asyncio
from datetime import datetime

from app.config import get_settings

websocket_router = APIRouter()

# Connection manager for WebSocket clients
class ConnectionManager:
    """Manages WebSocket connections for real-time updates."""
    
    def __init__(self):
        # Active connections by endpoint
        self.connections: Dict[str, Set[WebSocket]] = {
            "monitoring": set(),
            "logs": set(),
            "alerts": set()
        }
    
    async def connect(self, websocket: WebSocket, endpoint: str):
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        if endpoint not in self.connections:
            self.connections[endpoint] = set()
        self.connections[endpoint].add(websocket)
        print(f"📡 New WebSocket connection to /{endpoint}, total: {len(self.connections[endpoint])}")
    
    def disconnect(self, websocket: WebSocket, endpoint: str):
        """Remove a WebSocket connection."""
        if endpoint in self.connections:
            self.connections[endpoint].discard(websocket)
            print(f"📡 WebSocket disconnected from /{endpoint}, remaining: {len(self.connections[endpoint])}")
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Send message to specific WebSocket."""
        try:
            await websocket.send_text(message)
        except:
            # Connection might be closed
            pass
    
    async def broadcast_to_endpoint(self, message: str, endpoint: str):
        """Broadcast message to all connections on an endpoint."""
        if endpoint not in self.connections:
            return
        
        disconnected = set()
        for connection in self.connections[endpoint]:
            try:
                await connection.send_text(message)
            except:
                # Mark for removal if connection is dead
                disconnected.add(connection)
        
        # Clean up dead connections
        for conn in disconnected:
            self.connections[endpoint].discard(conn)
    
    async def broadcast_to_all(self, message: str):
        """Broadcast message to all connected clients."""
        for endpoint in self.connections:
            await self.broadcast_to_endpoint(message, endpoint)
    
    def get_connection_count(self) -> Dict[str, int]:
        """Get count of active connections by endpoint."""
        return {endpoint: len(conns) for endpoint, conns in self.connections.items()}

# Global connection manager
manager = ConnectionManager()


@websocket_router.websocket("/monitoring")
async def websocket_monitoring(websocket: WebSocket):
    """WebSocket for real-time monitoring dashboard updates."""
    await manager.connect(websocket, "monitoring")
    
    try:
        # Send initial connection confirmation
        await websocket.send_text(json.dumps({
            "type": "connection",
            "status": "connected",
            "endpoint": "monitoring",
            "timestamp": datetime.utcnow().isoformat()
        }))
        
        # Send initial stats
        # TODO: Replace with actual stats in Phase 2.5
        initial_stats = {
            "type": "stats_update",
            "data": {
                "total_logs": 0,
                "error_rate": 0.0,
                "avg_latency": None,
                "active_anomalies": 0,
                "alerts_sent": 0,
                "connections": manager.get_connection_count()
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        await websocket.send_text(json.dumps(initial_stats))
        
        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for client messages (heartbeat, subscriptions, etc.)
                data = await websocket.receive_text()
                message = json.loads(data)
                
                if message.get("type") == "heartbeat":
                    await websocket.send_text(json.dumps({
                        "type": "heartbeat_ack",
                        "timestamp": datetime.utcnow().isoformat()
                    }))
                
                elif message.get("type") == "subscribe":
                    # Handle subscription to specific data streams
                    streams = message.get("streams", [])
                    await websocket.send_text(json.dumps({
                        "type": "subscription_ack",
                        "streams": streams,
                        "timestamp": datetime.utcnow().isoformat()
                    }))
                
            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                # Invalid JSON, send error
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Invalid JSON format",
                    "timestamp": datetime.utcnow().isoformat()
                }))
            except Exception as e:
                # Other errors
                await websocket.send_text(json.dumps({
                    "type": "error", 
                    "message": f"Server error: {str(e)}",
                    "timestamp": datetime.utcnow().isoformat()
                }))
    
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket, "monitoring")


@websocket_router.websocket("/logs")
async def websocket_logs(websocket: WebSocket):
    """WebSocket for real-time log streaming."""
    await manager.connect(websocket, "logs")
    
    try:
        # Send connection confirmation
        await websocket.send_text(json.dumps({
            "type": "connection",
            "status": "connected", 
            "endpoint": "logs",
            "message": "Connected to log stream",
            "timestamp": datetime.utcnow().isoformat()
        }))
        
        # Handle client messages and filters
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                
                if message.get("type") == "set_filter":
                    # Client wants to filter logs
                    filters = message.get("filters", {})
                    await websocket.send_text(json.dumps({
                        "type": "filter_set",
                        "filters": filters,
                        "message": "Log filters applied",
                        "timestamp": datetime.utcnow().isoformat()
                    }))
                
                elif message.get("type") == "heartbeat":
                    await websocket.send_text(json.dumps({
                        "type": "heartbeat_ack",
                        "timestamp": datetime.utcnow().isoformat()
                    }))
                    
            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Invalid JSON format"
                }))
    
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket, "logs")


@websocket_router.websocket("/alerts")
async def websocket_alerts(websocket: WebSocket):
    """WebSocket for real-time alert notifications."""
    await manager.connect(websocket, "alerts")
    
    try:
        # Send connection confirmation
        await websocket.send_text(json.dumps({
            "type": "connection",
            "status": "connected",
            "endpoint": "alerts", 
            "message": "Connected to alert stream",
            "timestamp": datetime.utcnow().isoformat()
        }))
        
        # Handle client messages
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                
                if message.get("type") == "heartbeat":
                    await websocket.send_text(json.dumps({
                        "type": "heartbeat_ack",
                        "timestamp": datetime.utcnow().isoformat()
                    }))
                
                elif message.get("type") == "subscribe_alerts":
                    # Client wants to subscribe to specific alert types
                    alert_types = message.get("alert_types", [])
                    await websocket.send_text(json.dumps({
                        "type": "alert_subscription_ack",
                        "alert_types": alert_types,
                        "timestamp": datetime.utcnow().isoformat()
                    }))
                    
            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Invalid JSON format"
                }))
    
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket, "alerts")


# Utility functions for broadcasting (to be used by services)

async def broadcast_log_entry(log_entry: dict):
    """Broadcast new log entry to all log stream clients."""
    message = {
        "type": "new_log",
        "data": log_entry,
        "timestamp": datetime.utcnow().isoformat()
    }
    await manager.broadcast_to_endpoint(json.dumps(message), "logs")


async def broadcast_anomaly_detected(anomaly: dict):
    """Broadcast anomaly detection to monitoring clients."""
    message = {
        "type": "anomaly_detected",
        "data": anomaly,
        "timestamp": datetime.utcnow().isoformat()
    }
    await manager.broadcast_to_endpoint(json.dumps(message), "monitoring")


async def broadcast_alert_generated(alert: dict):
    """Broadcast new alert to alert stream clients."""
    message = {
        "type": "alert_generated",
        "data": alert,
        "timestamp": datetime.utcnow().isoformat()
    }
    await manager.broadcast_to_endpoint(json.dumps(message), "alerts")


async def broadcast_stats_update(stats: dict):
    """Broadcast monitoring statistics update."""
    message = {
        "type": "stats_update",
        "data": stats,
        "timestamp": datetime.utcnow().isoformat()
    }
    await manager.broadcast_to_endpoint(json.dumps(message), "monitoring")


async def broadcast_system_status(status: dict):
    """Broadcast system status changes."""
    message = {
        "type": "system_status",
        "data": status,
        "timestamp": datetime.utcnow().isoformat()
    }
    await manager.broadcast_to_all(json.dumps(message))


# Background task for periodic updates (will be used in Phase 2.5)
async def periodic_stats_broadcaster():
    """Background task to send periodic stats updates."""
    settings = get_settings()
    
    while True:
        try:
            # TODO: Get actual stats from monitoring engine in Phase 2.5
            stats = {
                "total_logs": 0,
                "error_rate": 0.0,
                "avg_latency": None,
                "active_anomalies": 0,
                "alerts_sent": 0,
                "connections": manager.get_connection_count(),
                "system_health": "healthy"
            }
            
            await broadcast_stats_update(stats)
            
            # Wait for next update interval
            await asyncio.sleep(settings.websocket_heartbeat_interval)
            
        except Exception as e:
            print(f"Error in stats broadcaster: {e}")
            await asyncio.sleep(10)  # Wait before retrying


# Export the connection manager for use by other services
__all__ = [
    "websocket_router", 
    "manager",
    "broadcast_log_entry",
    "broadcast_anomaly_detected", 
    "broadcast_alert_generated",
    "broadcast_stats_update",
    "broadcast_system_status"
]
