from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from ....services.chat import get_chat_service

router = APIRouter(prefix="/chat", tags=["chat"])


# Models


class Message(BaseModel):
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: datetime = None
    metadata: Optional[Dict[str, Any]] = None

    model_config = ConfigDict()


class ChatRequest(BaseModel):
    messages: List[Message]
    user_id: str
    conversation_id: Optional[str] = None


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

        # Resolve or create conversation
        if chat_request.conversation_id:
            conversation_id = chat_request.conversation_id
        else:
            conversation = await chat_service.create_conversation(user_id=chat_request.user_id)
            conversation_id = conversation.id

        # Persist the new user message to DB
        await chat_service.add_message(
            conversation_id=conversation_id,
            user_id=chat_request.user_id,
            content=last_message.content,
            role="user",
        )

        # Build DB-backed message history (exclude the last user message we just saved)
        history_items, total = await chat_service.get_conversation_history(conversation_id)
        history_payload: List[dict] = []
        # Exclude the last item if it's the user message we just added
        trimmed = history_items[:-1] if total > 0 else []
        for m in trimmed:
            # Normalize role to a raw string for downstream logic
            r = None
            try:
                r = m.role.value  # Enum -> value
            except Exception:
                r = m.role
            if isinstance(r, str):
                r = r.lower()
                # Handle possible Enum string representation like "MessageRole.ASSISTANT"
                if "." in r:
                    r = r.split(".")[-1]
            history_payload.append({"role": r, "content": m.content})

        # Generate assistant response via OpenAI
        assistant_msg = await chat_service.generate_response(
            conversation_id=conversation_id,
            user_id=chat_request.user_id,
            message=last_message.content,
            message_history=history_payload or None,
        )

        # Map to API response model expected by frontend
        response_message = Message(
            role="assistant",
            content=assistant_msg.content,
            timestamp=getattr(assistant_msg, "created_at", None) or datetime.now(timezone.utc),
            metadata=getattr(assistant_msg, "metadata", None) or {},
        )

        return {
            "message": response_message,
            "conversation_id": conversation_id,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
