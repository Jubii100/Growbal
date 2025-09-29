#!/usr/bin/env python3
"""Test the complete chat flow"""

import sys
import os
import asyncio

# Add the project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from chat.session_manager import session_manager

async def test_complete_flow():
    """Test creating a session and processing a message"""
    
    print("🧪 Testing complete chat flow...")
    
    # Step 1: Create a session
    session_id, session_data, is_new = await session_manager.get_or_create_session(
        country="USA",
        service_type="Tax Services"
    )
    print(f"✅ Session created: {session_id[:8]}")
    
    # Step 2: Simulate message processing (similar to the chat wrapper)
    message = "Hello, I need help with tax services"
    
    # Store user message
    await session_manager.add_message(session_id, "user", message)
    print(f"✅ User message stored")
    
    # Generate response
    response = f"Hello! I can help you find tax services in USA. You said: '{message}'"
    
    # Store assistant response
    await session_manager.add_message(session_id, "assistant", response)
    print(f"✅ Assistant response stored")
    
    # Step 3: Verify history
    history = await session_manager.get_session_history_gradio(session_id)
    print(f"✅ History retrieved: {len(history)} messages")
    
    for i, msg in enumerate(history):
        print(f"   {i+1}. {msg['role'].upper()}: {msg['content'][:50]}...")
    
    return session_id

if __name__ == "__main__":
    asyncio.run(test_complete_flow())