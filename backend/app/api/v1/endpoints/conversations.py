from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from ....models.conversation import (
    Conversation,
    ConversationCreate,
    ConversationList,
    ConversationUpdate,
    Message,
    MessageCreate,
    MessageList,
)
from ....models.user import User
from ....core.security import get_current_active_user
from ....services.chat import ChatService, get_chat_service

router = APIRouter()


@router.post("/", response_model=Conversation, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    conversation_in: ConversationCreate,
    current_user: User = Depends(get_current_active_user),
    chat_service: ChatService = Depends(get_chat_service),
) -> Any:
    """
    Create a new conversation.

    Args:
        conversation_in: Conversation creation data
        current_user: The current authenticated user
        chat_service: Chat service

    Returns:
        Conversation: The created conversation
    """
    import logging
    import traceback
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    try:
        logger.info(f"Creating conversation with user_id={current_user.id}, title={conversation_in.title}")
        logger.info(f"Current user ID: {current_user.id}, email: {current_user.email}")
        logger.info(f"Conversation data: {conversation_in}")

        # Print detailed metadata about objects for debugging
        logger.info(f"User ID type: {type(current_user.id)}, value: '{current_user.id}'")
        logger.info(f"Current user dictionary: {current_user.__dict__}")

        conversation = await chat_service.create_conversation(
            user_id=current_user.id,
            title=conversation_in.title,
            metadata=conversation_in.metadata,
        )
        logger.info(f"Successfully created conversation: {conversation}")
        return conversation
    except Exception as e:
        logger.error(f"Error creating conversation: {str(e)}")
        logger.error(traceback.format_exc())  # Detailed stack trace
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating conversation: {str(e)}"
        )


@router.get("/", response_model=ConversationList)
async def list_conversations(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    chat_service: ChatService = Depends(get_chat_service),
) -> Any:
    """
    List conversations for the current user.

    Args:
        skip: Number of conversations to skip
        limit: Maximum number of conversations to return
        current_user: The current authenticated user
        chat_service: Chat service

    Returns:
        ConversationList: List of conversations with pagination info
    """
    conversations, total = await chat_service.get_user_conversations(
        user_id=current_user.id, skip=skip, limit=limit
    )
    # Map offset pagination to page/page_size for response model
    page = (skip // limit) + 1 if limit and limit > 0 else 1
    page_size = limit if limit and limit > 0 else total
    return ConversationList(
        items=conversations,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{conversation_id}", response_model=Conversation)
async def get_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_active_user),
    chat_service: ChatService = Depends(get_chat_service),
) -> Any:
    """
    Get a conversation by ID.

    Args:
        conversation_id: ID of the conversation to retrieve
        current_user: The current authenticated user
        chat_service: Chat service

    Returns:
        Conversation: The requested conversation

    Raises:
        HTTPException: If the conversation is not found or access is denied
    """
    conversation = await chat_service.get_conversation(conversation_id)
    if not conversation or conversation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found"
        )
    return conversation


@router.put("/{conversation_id}", response_model=Conversation)
async def update_conversation(
    conversation_id: str,
    conversation_in: ConversationUpdate,
    current_user: User = Depends(get_current_active_user),
    chat_service: ChatService = Depends(get_chat_service),
) -> Any:
    """
    Update a conversation.

    Args:
        conversation_id: ID of the conversation to update
        conversation_in: Conversation update data
        current_user: The current authenticated user
        chat_service: Chat service

    Returns:
        Conversation: The updated conversation

    Raises:
        HTTPException: If the conversation is not found or access is denied
    """
    # Verify the conversation exists and belongs to the user
    conversation = await chat_service.get_conversation(conversation_id)
    if not conversation or conversation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found"
        )

    # Update the conversation
    updated_conversation = await chat_service.update_conversation(
        conversation_id=conversation_id,
        user_id=current_user.id,
        **conversation_in.dict(exclude_unset=True),
    )
    return updated_conversation


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_active_user),
    chat_service: ChatService = Depends(get_chat_service),
) -> None:
    """
    Delete a conversation.

    Args:
        conversation_id: ID of the conversation to delete
        current_user: The current authenticated user
        chat_service: Chat service

    Raises:
        HTTPException: If the conversation is not found or access is denied
    """
    conversation = await chat_service.get_conversation(conversation_id)
    if not conversation or conversation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found"
        )
    await chat_service.delete_conversation(conversation_id)


@router.post("/{conversation_id}/messages", response_model=Message, status_code=status.HTTP_201_CREATED)
async def create_message(
    conversation_id: str,
    message_in: MessageCreate,
    current_user: User = Depends(get_current_active_user),
    chat_service: ChatService = Depends(get_chat_service),
) -> Any:
    """
    Send a message in a conversation and get a response.

    Args:
        conversation_id: ID of the conversation
        message_in: The message to send
        current_user: The current authenticated user
        chat_service: Chat service

    Returns:
        Message: The assistant's response message

    Raises:
        HTTPException: If the conversation is not found or access is denied
    """
    # Verify the conversation exists and belongs to the user
    conversation = await chat_service.get_conversation(conversation_id)
    if not conversation or conversation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found"
        )

    # Add the user's message
    await chat_service.add_message(
        conversation_id=conversation_id,
        user_id=current_user.id,
        content=message_in.content,
        role="user",
        message_type="text",
        metadata=message_in.metadata,
    )

    # Generate a response
    response = await chat_service.generate_response(
        conversation_id=conversation_id,
        user_id=current_user.id,
        message=message_in.content,
    )

    return response


@router.get("/{conversation_id}/messages", response_model=MessageList)
async def list_messages(
    conversation_id: str,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    chat_service: ChatService = Depends(get_chat_service),
) -> Any:
    """
    List messages in a conversation.

    Args:
        conversation_id: ID of the conversation
        skip: Number of messages to skip
        limit: Maximum number of messages to return
        current_user: The current authenticated user
        chat_service: Chat service

    Returns:
        MessageList: List of messages with pagination info

    Raises:
        HTTPException: If the conversation is not found or access is denied
    """
    # Verify the conversation exists and belongs to the user
    conversation = await chat_service.get_conversation(conversation_id)
    if not conversation or conversation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found"
        )

    # Get messages
    messages, total = await chat_service.get_conversation_history(
        conversation_id=conversation_id, skip=skip, limit=limit
    )
    # Map offset pagination to page/page_size for response model
    page = (skip // limit) + 1 if limit and limit > 0 else 1
    page_size = limit if limit and limit > 0 else total
    return MessageList(
        items=messages,
        total=total,
        page=page,
        page_size=page_size,
        conversation_id=conversation_id,
    )
