"""
Telegram Command Handlers Module
Organizes Telegram bot commands into logical groups for maintainability
"""
from typing import Dict, Callable, Any, Optional
import logging

logger = logging.getLogger(__name__)

# Command registry - maps command patterns to handlers
COMMAND_HANDLERS: Dict[str, Callable] = {}

def register_command(patterns: list):
    """Decorator to register command handlers"""
    def decorator(func):
        for pattern in patterns:
            COMMAND_HANDLERS[pattern.lower()] = func
        return func
    return decorator

async def handle_command(text: str, chat_id: int, context: dict) -> Optional[tuple]:
    """
    Route incoming text to appropriate command handler.
    Returns (response, context_type) or None if not a registered command.
    """
    text_lower = text.lower().strip()
    
    # Try exact match first
    if text_lower in COMMAND_HANDLERS:
        return await COMMAND_HANDLERS[text_lower](text, chat_id, context)
    
    # Try prefix match for commands with arguments
    for pattern, handler in COMMAND_HANDLERS.items():
        if text_lower.startswith(pattern + ' '):
            return await handler(text, chat_id, context)
    
    return None

# Import command modules to register handlers
# These will be imported when the module loads
