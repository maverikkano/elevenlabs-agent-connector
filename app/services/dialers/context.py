"""
Context management utilities for dialer sessions

Provides in-memory storage for call contexts. In production, consider using Redis.
"""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# In-memory storage for call contexts
_call_contexts: Dict[str, Dict] = {}


def store_call_context(call_id: str, context: Dict) -> None:
    """
    Store context for a call session

    Args:
        call_id: Unique call identifier
        context: Context data to store
    """
    _call_contexts[call_id] = context
    logger.info(f"📦 Stored context for call {call_id}")


def get_call_context(call_id: str) -> Optional[Dict]:
    """
    Retrieve context for a call session

    Args:
        call_id: Unique call identifier

    Returns:
        Context dict if found, None otherwise
    """
    context = _call_contexts.get(call_id)
    if context:
        logger.debug(f"📦 Retrieved context for call {call_id}")
    else:
        logger.debug(f"📦 No context found for call {call_id}")
    return context


def cleanup_call_context(call_id: str) -> None:
    """
    Remove context for a call session

    Args:
        call_id: Unique call identifier
    """
    if call_id in _call_contexts:
        del _call_contexts[call_id]
        logger.info(f"🗑️ Cleaned up context for call {call_id}")


def clear_all_contexts() -> None:
    """Clear all stored contexts (useful for testing)"""
    _call_contexts.clear()
    logger.info("🗑️ Cleared all call contexts")


def get_all_context_ids() -> list:
    """
    Get all stored call IDs

    Returns:
        List of call IDs
    """
    return list(_call_contexts.keys())
