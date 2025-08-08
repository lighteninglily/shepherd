from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from datetime import datetime
from app.services.chat import get_chat_service

router = APIRouter(prefix="/chat", tags=["chat"])


# Models


class Message(BaseModel):
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: datetime = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ChatRequest(BaseModel):
    messages: List[Message]
    user_id: str


class ChatResponse(BaseModel):
    message: Message
    conversation_id: str


# Temporary in-memory storage for conversations (replace with database in production)
conversations = {}


@router.post("", response_model=ChatResponse)
async def chat(chat_request: ChatRequest):
    """
    Process a chat message and return the AI's response.
    """
    try:
        # Get the last user message
        if not chat_request.messages:
            raise HTTPException(status_code=400, detail="No messages provided")

        last_message = chat_request.messages[-1]

        # Initialize chat service
        chat_service = get_chat_service()

        # Create a conversation per request (can be optimized to reuse later)
        conversation = await chat_service.create_conversation(user_id=chat_request.user_id)

        # Prepare message history excluding the last user message
        history: List[dict] = []
        if len(chat_request.messages) > 1:
            for m in chat_request.messages[:-1]:
                # Only pass role/content to the model
                history.append({"role": m.role, "content": m.content})

        # Generate assistant response via OpenAI
        assistant_msg = await chat_service.generate_response(
            conversation_id=conversation.id,
            user_id=chat_request.user_id,
            message=last_message.content,
            message_history=history or None,
        )

        # Map to API response model expected by frontend
        response_message = Message(
            role="assistant",
            content=assistant_msg.content,
            timestamp=getattr(assistant_msg, "created_at", None) or datetime.utcnow(),
        )

        return {
            "message": response_message,
            "conversation_id": conversation.id,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
