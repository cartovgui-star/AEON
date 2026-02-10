"""
WebSocket Manager for Real-time Alerts
Handles WebSocket connections and broadcasts alerts to connected clients
"""
import asyncio
import logging
from typing import Set, Dict, Any
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime, timezone
import json

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages WebSocket connections for real-time updates"""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.connection_count = 0
        self.messages_sent = 0
    
    async def connect(self, websocket: WebSocket):
        """Accept and track a new WebSocket connection"""
        await websocket.accept()
        self.active_connections.add(websocket)
        self.connection_count += 1
        logger.info(f"WebSocket connected. Total: {len(self.active_connections)}")
        
        # Send welcome message
        await self.send_personal(websocket, {
            "type": "connected",
            "message": "Connected to Aeon real-time alerts",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection"""
        self.active_connections.discard(websocket)
        logger.info(f"WebSocket disconnected. Total: {len(self.active_connections)}")
    
    async def send_personal(self, websocket: WebSocket, data: Dict[str, Any]):
        """Send message to a specific client"""
        try:
            await websocket.send_json(data)
            self.messages_sent += 1
        except Exception as e:
            logger.error(f"Error sending to websocket: {e}")
            self.disconnect(websocket)
    
    async def broadcast(self, data: Dict[str, Any]):
        """Broadcast message to all connected clients"""
        if not self.active_connections:
            return
        
        data["timestamp"] = datetime.now(timezone.utc).isoformat()
        
        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_json(data)
                self.messages_sent += 1
            except Exception as e:
                logger.error(f"Broadcast error: {e}")
                disconnected.add(connection)
        
        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)
    
    async def broadcast_alert(self, alert_type: str, symbol: str, message: str, 
                               data: Dict = None, severity: str = "medium"):
        """Broadcast a price alert to all clients"""
        await self.broadcast({
            "type": "alert",
            "alert_type": alert_type,
            "symbol": symbol,
            "message": message,
            "data": data or {},
            "severity": severity
        })
    
    async def broadcast_trade(self, trade_data: Dict):
        """Broadcast a trade update"""
        await self.broadcast({
            "type": "trade",
            "trade": trade_data
        })
    
    async def broadcast_strategy_signal(self, signal_data: Dict):
        """Broadcast a strategy signal"""
        await self.broadcast({
            "type": "strategy_signal",
            "signal": signal_data
        })
    
    async def broadcast_smc_update(self, smc_data: Dict):
        """Broadcast SMC analysis update"""
        await self.broadcast({
            "type": "smc_update",
            "smc": smc_data
        })
    
    def get_stats(self) -> Dict:
        """Get WebSocket manager statistics"""
        return {
            "active_connections": len(self.active_connections),
            "total_connections": self.connection_count,
            "messages_sent": self.messages_sent
        }


# Global instance
ws_manager = WebSocketManager()
