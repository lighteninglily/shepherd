#!/usr/bin/env python3

import asyncio
import sys
import os
import logging

# Add the backend directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from backend.app.services.chat import get_chat_service
from backend.app.db.base import SessionLocal
from backend.app.models.sql_models import Conversation as SQLConversation

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def test_intake_completion():
    """Test intake completion persistence directly."""
    
    # Initialize chat service
    chat_service = get_chat_service()
    
    # Create a conversation
    conversation = await chat_service.create_conversation(user_id="debug-user")
    conversation_id = conversation.id
    
    print(f"Created conversation: {conversation_id}")
    
    # Add initial user message
    await chat_service.add_message(
        conversation_id=conversation_id,
        user_id="debug-user",
        content="We argue a lot lately.",
        role="user"
    )
    
    # Generate first assistant response
    response1 = await chat_service.generate_response(
        conversation_id=conversation_id,
        user_id="debug-user", 
        message="We argue a lot lately."
    )
    
    print(f"Response 1 metadata: {response1.metadata}")
    
    # Add another user message asking for advice
    await chat_service.add_message(
        conversation_id=conversation_id,
        user_id="debug-user",
        content="What should I do next?",
        role="user"
    )
    
    # Generate second assistant response (should trigger wrap-up gating)
    response2 = await chat_service.generate_response(
        conversation_id=conversation_id,
        user_id="debug-user",
        message="What should I do next?"
    )
    
    print(f"Response 2 metadata: {response2.metadata}")
    intake2 = response2.metadata.get("intake", {})
    print(f"Response 2 intake completed: {intake2.get('completed')}")
    
    # Add wrap-up affirmation message
    await chat_service.add_message(
        conversation_id=conversation_id,
        user_id="debug-user", 
        content="That's enough, I'm ready for advice.",
        role="user"
    )
    
    # Generate third assistant response (should flip intake completion)
    response3 = await chat_service.generate_response(
        conversation_id=conversation_id,
        user_id="debug-user",
        message="That's enough, I'm ready for advice."
    )
    
    print(f"Response 3 metadata: {response3.metadata}")
    intake3 = response3.metadata.get("intake", {})
    print(f"Response 3 intake completed: {intake3.get('completed')}")
    
    # Check conversation metadata in DB
    db = SessionLocal()
    try:
        row = db.query(SQLConversation).filter(SQLConversation.id == conversation_id).first()
        if row:
            conv_meta = getattr(row, "metadata_json", {}) or {}
            intake_meta = conv_meta.get("intake", {})
            print(f"DB conversation metadata: {conv_meta}")
            print(f"DB intake completed: {intake_meta.get('completed')}")
        else:
            print("No conversation found in DB")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_intake_completion())
