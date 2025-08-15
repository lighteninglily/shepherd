import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import json
import urllib.request
import urllib.error
import os
import inspect
import re
from pathlib import Path
from sqlalchemy.orm.attributes import flag_modified

# Optional orchestrator (feature-flagged)
from ..orchestration.graph import Orchestrator, TurnState
from ..policies.intake import IntakeState
from ..orchestration.metadata import normalize_meta
from ..orchestration.classify import classify
from ..orchestration.scrubber import scrub_books_if_gated

from ..config import get_settings
from ..models.conversation import (
    Conversation,
    Message,
    MessageRole,
    MessageType,
    ConversationStatus,
)

# Configure logging
logger = logging.getLogger(__name__)


class ChatService:
    """Service for handling chat functionality with OpenAI's API."""

    def __init__(self):
        try:
            logger.warning(
                "ChatService module file: __file__=%s class_file=%s",
                __file__, inspect.getfile(self.__class__)
            )
        except Exception:
            pass
        self.model = "gpt-4o-mini"  # Default model with broad availability
        self.temperature = 0.7
        self.max_tokens = 1000
        self.presence_penalty = 0.6
        self.frequency_penalty = 0.6

        # Load settings and API key. We log masked info to diagnose precedence issues.
        settings = get_settings()
        # Persist settings on the instance for later use in generate_response
        self.settings = settings
        # Apply unified configuration from settings (overriding local defaults)
        try:
            self.model = getattr(settings, "MODEL_NAME", self.model) or self.model
            self.temperature = float(getattr(settings, "TEMPERATURE", self.temperature))
            self.max_tokens = int(getattr(settings, "MAX_TOKENS", self.max_tokens))
            self.presence_penalty = float(getattr(settings, "PRESENCE_PENALTY", self.presence_penalty))
            self.frequency_penalty = float(getattr(settings, "FREQUENCY_PENALTY", self.frequency_penalty))
        except Exception:
            # If any casting fails, keep safe defaults
            pass

        logger.info(
            "ChatService config: model=%s temperature=%s max_tokens=%s presence_penalty=%s frequency_penalty=%s",
            self.model, self.temperature, self.max_tokens, self.presence_penalty, self.frequency_penalty,
        )

        settings_key = (settings.OPENAI_API_KEY or "").strip()
        env_key = (os.getenv("OPENAI_API_KEY") or "").strip()
        file_key = ""
        try:
            # Read first occurrence in backend/.env explicitly (backend/.env)
            backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            env_path = os.path.join(backend_dir, ".env")
            if os.path.exists(env_path):
                with open(env_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if line.startswith("OPENAI_API_KEY="):
                            file_key = line.split("=", 1)[1].strip()
                            break
        except Exception:
            file_key = ""

        def mask(k: str) -> str:
            return f"len={len(k)} {k[:7]}...{k[-4:]}" if k else "<empty>"

        logger.warning(
            "OpenAI key sources (masked): file=%s settings=%s env=%s (env_path=%s)",
            mask(file_key), mask(settings_key), mask(env_key), env_path
        )

        # Choose key (prefer .env file explicitly, then settings, then env var)
        api_key = file_key or settings_key or env_key
        if not api_key:
            logger.error("OPENAI_API_KEY is not set. Please configure it in backend/.env")
        else:
            logger.warning("Using OpenAI key (masked): %s", mask(api_key))
        self.api_key = api_key

        # System prompt for Shepherd AI
        self.system_prompt = """
        You are Shepherd, an AI pastoral companion created by The Way — a church community
        centered on wholehearted worship, deep joy in Jesus, devotion to the Word,
        brave love, and authentic community.

        Your mission is to gently and truthfully walk with people through their spiritual
        journey — especially in times of pain, doubt, guilt, longing, and growth.
        Speak like a warm, wise pastor who knows the Bible, listens deeply, and loves
        people as Jesus does.

        Your personality and posture should reflect these values:
        1. **Wholehearted Worshippers of Jesus**
           Help people see Jesus as worthy of their full attention, affection, and surrender.
           Encourage awe, wonder, repentance, and worship.

        2. **People Who Truly Enjoy Jesus**
           Don't just teach — help them taste and see that He is good.
           Invite people to encounter joy, not just obedience.

        3. **People Devoted to the Word**
           Anchor every conversation in Scripture. Help people engage with the Bible —
           not as dry text, but as living truth that leads to life.

        4. **People Made Brave by the Love of Jesus**
           Speak courage into people's fears. When someone feels unworthy, afraid,
           or stuck in shame, remind them of the power of Jesus' love to free and transform.

        5. **A Community Built on Genuine Love**
           You are not a replacement for real relationships. Always remind people that
           following Jesus happens best in community. Invite them into connection —
           not isolation.

        Your voice should be:
        - Gentle, like a good shepherd
        - Humble, never harsh or superior
        - Emotionally intelligent
        - Scripturally grounded
        - Compassionate, especially toward the broken
        - Always pointing to Jesus, not to yourself

        You may:
        - Suggest reading the Bible together (e.g., "Let's look at Romans 8")
        - Offer to forward the user's prayer request to a praying partner (human) with explicit consent
        - Guide users through spiritual journeys
        - Explain Scripture in plain language with warmth and depth

        You must not:
        - Pretend to be human or offer supernatural revelation
        - Offer mental health diagnoses, medical advice, or emergency help
        - Replace real pastors, community, or church — always affirm their role
        - Argue or shame. Correct with grace and truth.
        - Pray directly or offer to pray yourself — only forward prayer requests to human praying partners
        """

        # Load topic rules (lightweight registry)
        try:
            rules_dir = Path(__file__).resolve().parents[1] / "pastoral" / "rules"
            self.topic_rules: Dict[str, Any] = {}
            marriage_path = rules_dir / "marriage.json"
            if marriage_path.exists():
                with open(marriage_path, "r", encoding="utf-8") as f:
                    self.topic_rules["marriage"] = json.load(f)
            logger.info("Loaded topic rules: %s", list(self.topic_rules.keys()))
        except Exception as _e:
            self.topic_rules = {}
            logger.warning("Failed to load topic rules: %s", _e)

    async def create_conversation(  # noqa: C901
        self, user_id: str, title: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None
    ) -> Conversation:
        """Create a new conversation with DB persistence."""
        from ..models.sql_models import Conversation as SQLConversation
        from ..db.base import SessionLocal, engine

        import logging
        import sys
        from sqlalchemy.exc import SQLAlchemyError
        import traceback

        # Setup direct console printing for immediate visibility
        def print_debug(message):
            print(f"DEBUG_CONVO: {message}", flush=True)
            sys.stderr.flush()  # Ensure stderr is flushed

        print_debug("====== BEGIN create_conversation ======")
        print_debug(f"user_id: {user_id!r}, title: {title!r}, metadata: {metadata!r}")

        logger = logging.getLogger(__name__)
        logger.setLevel(logging.DEBUG)

        # Validate user_id
        if not user_id:
            error_msg = "Cannot create conversation: user_id is None or empty"
            print_debug(f"ERROR: {error_msg}")
            logger.error(error_msg)
            raise ValueError("user_id is required")

        # Check that the database engine and connection are working
        try:
            # Test the engine connection
            connection = engine.connect()
            connection.close()
            print_debug("Database engine connection test: SUCCESS")
        except Exception as e:
            print_debug(f"Database engine connection test: FAILED - {str(e)}")
            print_debug(traceback.format_exc())
            raise

        # Use a default title if none is provided
        if not title:
            title = f"Conversation {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}"
            print_debug(f"No title provided, using default: {title}")

        db = None
        try:
            # Create database session
            print_debug("Creating database session")
            db = SessionLocal()

            try:
                # Create SQLConversation object
                print_debug("Creating conversation object")
                db_conversation = SQLConversation(
                    user_id=user_id,
                    title=title,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                    metadata_json=(metadata or {}),
                )

                # Add to session and commit
                print_debug("Adding conversation to database session")
                db.add(db_conversation)

                print_debug("Committing transaction")
                db.commit()

                print_debug("Refreshing object")
                db.refresh(db_conversation)

                print_debug(f"Successfully created conversation with ID: {db_conversation.id}")

                # Convert to API model
                conversation = Conversation(
                    id=db_conversation.id,
                    user_id=user_id,
                    title=title,
                    created_at=db_conversation.created_at,
                    updated_at=db_conversation.updated_at,
                    status="active",
                    metadata=db_conversation.metadata_json or {},
                )

                print_debug(f"Created Conversation response: {conversation}")
                print_debug("====== END create_conversation (success) ======")
                return conversation

            except SQLAlchemyError as e:
                if db:
                    print_debug("Rolling back transaction due to database error")
                    db.rollback()
                error_msg = f"Database error: {str(e)}"
                print_debug(f"ERROR: {error_msg}")
                print_debug(traceback.format_exc())
                logger.error(error_msg)
                raise

        except Exception as e:
            error_msg = f"Error in create_conversation: {str(e)}"
            print_debug(f"ERROR: {error_msg}")
            print_debug(traceback.format_exc())
            logger.error(error_msg)
            raise

        finally:
            if db:
                print_debug("Closing database session")
                db.close()

        print_debug("====== END create_conversation (unexpected exit) ======")
        raise RuntimeError("Unexpected code path in create_conversation")

    async def add_message(
        self,
        conversation_id: str,
        user_id: str,
        content: str,
        role: MessageRole = MessageRole.USER,
        message_type: MessageType = MessageType.TEXT,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Message:
        """Add a message to a conversation with DB persistence."""
        from ..models.sql_models import Message as SQLMessage
        from ..db.base import SessionLocal
        db = SessionLocal()
        try:
            db_msg = SQLMessage(
                conversation_id=conversation_id,
                role=role.value if hasattr(role, "value") else str(role),
                content=content,
                created_at=datetime.now(timezone.utc),
                metadata_json=(metadata or {}),
            )
            db.add(db_msg)
            db.commit()
            db.refresh(db_msg)
            return Message(
                id=db_msg.id,
                conversation_id=conversation_id,
                user_id=user_id,
                role=db_msg.role,
                content=db_msg.content,
                created_at=db_msg.created_at,
                metadata=db_msg.metadata_json or {},
            )
        finally:
            db.close()
            try:
                # Prevent scoped_session from caching objects across calls
                SessionLocal.remove()  # type: ignore[name-defined]
            except Exception:
                pass
            try:
                # Prevent scoped_session from caching objects across calls
                SessionLocal.remove()  # type: ignore[name-defined]
            except Exception:
                pass

    async def get_user_conversations(self, user_id: str, skip: int = 0, limit: int = 100) -> tuple[list[Conversation], int]:
        """Return a user's conversations with pagination and total count."""
        from ..models.sql_models import Conversation as SQLConversation
        from ..db.base import SessionLocal
        db = SessionLocal()
        try:
            q = db.query(SQLConversation).filter(SQLConversation.user_id == user_id)
            total = q.count()
            rows = (
                q.order_by(SQLConversation.created_at.desc())
                .offset(skip)
                .limit(limit)
                .all()
            )
            items: list[Conversation] = []
            for r in rows:
                items.append(
                    Conversation(
                        id=r.id,
                        user_id=r.user_id,
                        title=r.title,
                        status="active" if getattr(r, "is_active", True) else "archived",
                        created_at=r.created_at,
                        updated_at=r.updated_at,
                        metadata=(getattr(r, "metadata_json", None) or {}),
                    )
                )
            return items, total
        finally:
            db.close()

    def _get_turn_indexes(self, conversation_id: str) -> tuple[int, int, str]:
        """Compute assistant/user turn indexes and last assistant text from DB."""
        from ..models.sql_models import Message as SQLMessage
        from ..db.base import SessionLocal
        db = SessionLocal()
        try:
            rows = (
                db.query(SQLMessage)
                .filter(SQLMessage.conversation_id == conversation_id)
                .order_by(SQLMessage.created_at.asc())
                .all()
            )
            a = 0
            u = 0
            last_a_txt = ""
            for r in rows:
                if r.role == "assistant":
                    a += 1
                    last_a_txt = r.content or last_a_txt
                elif r.role == "user":
                    u += 1
            return a, u, last_a_txt
        finally:
            db.close()

    def _get_history_for_model(self, conversation_id: str, max_turns: int = 8) -> List[Dict[str, str]]:
        """Return [system_first] + last `max_turns` user/assistant turns (2*max_turns msgs)."""
        from ..models.sql_models import Message as SQLMessage
        from ..db.base import SessionLocal
        db = SessionLocal()
        try:
            rows = (
                db.query(SQLMessage)
                .filter(SQLMessage.conversation_id == conversation_id)
                .order_by(SQLMessage.created_at.asc())
                .all()
            )
            system_first: Optional[Dict[str, str]] = None
            ua: List[Dict[str, str]] = []
            for r in rows:
                if r.role == "system" and system_first is None:
                    system_first = {"role": "system", "content": r.content or ""}
                elif r.role in ("user", "assistant"):
                    ua.append({"role": r.role, "content": r.content or ""})
            trimmed = ua[-(max_turns * 2):]
            out: List[Dict[str, str]] = []
            if system_first:
                out.append(system_first)
            out.extend(trimmed)
            return out
        finally:
            db.close()

    async def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """Return a single conversation by ID or None."""
        from ..models.sql_models import Conversation as SQLConversation
        from ..db.base import SessionLocal
        db = SessionLocal()
        try:
            r = db.query(SQLConversation).filter(SQLConversation.id == conversation_id).first()
            if not r:
                return None
            return Conversation(
                id=r.id,
                user_id=r.user_id,
                title=r.title,
                status="active" if getattr(r, "is_active", True) else "archived",
                created_at=r.created_at,
                updated_at=r.updated_at,
                metadata=(getattr(r, "metadata_json", None) or {}),
            )
        finally:
            db.close()

    async def update_conversation(
        self,
        conversation_id: str,
        user_id: str,
        title: Optional[str] = None,
        status: Optional[ConversationStatus] = None,  # type: ignore[name-defined]
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Conversation:
        """Update a conversation's title/status/metadata."""
        from ..models.sql_models import Conversation as SQLConversation
        from ..db.base import SessionLocal
        db = SessionLocal()
        try:
            obj = db.query(SQLConversation).filter(SQLConversation.id == conversation_id).first()
            if not obj:
                raise ValueError("Conversation not found")
            if obj.user_id != user_id:
                raise ValueError("Forbidden")
            if title is not None:
                obj.title = title
            if status is not None:
                # Map Pydantic status to SQL boolean
                obj.is_active = True if str(status) == "active" or status == getattr(status, "ACTIVE", None) else False
            if metadata is not None:
                current = getattr(obj, "metadata_json", None) or {}
                # Deep merge provided metadata over current metadata
                def _deep_merge(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
                    out = dict(a or {})
                    for k, v in (b or {}).items():
                        if isinstance(v, dict) and isinstance(out.get(k), dict):
                            out[k] = _deep_merge(out[k], v)  # type: ignore[arg-type]
                        else:
                            out[k] = v
                    return out
                current = _deep_merge(current, metadata)
                obj.metadata_json = current
            obj.updated_at = datetime.now(timezone.utc)
            db.add(obj)
            db.commit()
            db.refresh(obj)
            return Conversation(
                id=obj.id,
                user_id=obj.user_id,
                title=obj.title,
                status="active" if getattr(obj, "is_active", True) else "archived",
                created_at=obj.created_at,
                updated_at=obj.updated_at,
                metadata=(getattr(obj, "metadata_json", None) or {}),
            )
        finally:
            db.close()
            try:
                # Ensure scoped_session does not retain stale identity map across requests
                SessionLocal.remove()  # type: ignore[name-defined]
            except Exception:
                pass

    async def delete_conversation(self, conversation_id: str) -> None:
        """Delete a conversation by ID (cascade deletes messages)."""
        from ..models.sql_models import Conversation as SQLConversation
        from ..db.base import SessionLocal
        db = SessionLocal()
        try:
            obj = db.query(SQLConversation).filter(SQLConversation.id == conversation_id).first()
            if not obj:
                return
            db.delete(obj)
            db.commit()
        finally:
            db.close()

    async def get_conversation_history(self, conversation_id: str, skip: int = 0, limit: int = 100) -> tuple[list[Message], int]:
        """Return messages for a conversation with pagination and total count."""
        from ..models.sql_models import Message as SQLMessage, Conversation as SQLConversation
        from ..db.base import SessionLocal
        db = SessionLocal()
        try:
            total = db.query(SQLMessage).filter(SQLMessage.conversation_id == conversation_id).count()
            rows = (
                db.query(SQLMessage)
                .filter(SQLMessage.conversation_id == conversation_id)
                .order_by(SQLMessage.created_at.asc())
                .offset(skip)
                .limit(limit)
                .all()
            )
            # Determine owner for user_id mapping when role == 'user'
            conv = db.query(SQLConversation).filter(SQLConversation.id == conversation_id).first()
            conv_user_id = conv.user_id if conv else ""
            items: list[Message] = []
            for r in rows:
                mapped_user_id = conv_user_id if r.role == "user" else ("assistant" if r.role == "assistant" else "system")
                items.append(
                    Message(
                        id=r.id,
                        conversation_id=r.conversation_id,
                        user_id=mapped_user_id,
                        role=r.role,
                        content=r.content,
                        created_at=r.created_at,
                        metadata=(getattr(r, "metadata_json", None) or {}),
                    )
                )
            return items, total
        finally:
            db.close()

    async def generate_response(
        self,
        conversation_id: str,
        user_id: str,
        message: str,
        message_history: Optional[List[Dict[str, str]]] = None,
    ) -> Message:
        """Generate a response to a user message.

        Args:
            conversation_id: ID of the conversation
            user_id: ID of the user sending the message
            message: The user's message
            message_history: Optional message history for context

        Returns:
            Message: The generated response message
        """
        try:
            logger.warning("generate_response: using direct HTTPS path with model=%s", self.model)

            # Build dynamic system instructions
            settings = get_settings()
            base_prompt = self.system_prompt
            messages = [{"role": "system", "content": base_prompt}]
            messages.append({
                "role": "system",
                "content": (
                    "DOMAIN FOCUS: This conversation is strictly about Christian marriage. "
                    "Frame every response within marriage and marital discipleship. "
                    "If a request is unrelated, gently refocus to marriage implications or kindly decline and invite a marriage-related topic."
                )
            })
            messages.append({
                "role": "system",
                "content": (
                    "CONVERSATIONAL STYLE GUIDE (friend_v1): Speak like a warm, supportive friend. "
                    "Begin by briefly reflecting their feelings and situation (empathic mirroring). "
                    "Keep replies to 2–5 short sentences in natural, conversational language. "
                    "Ask exactly one open, non-leading question at the end to invite sharing. "
                    "Avoid bullet lists or multi-step plans unless the user asks for them. "
                    "Scripture is optional; weave it gently and only when it truly fits, with a simple citation (e.g., 'James 1:19'). "
                    "Do not offer direct prayer; if they ask, offer to pass their request to a human prayer partner. "
                    "Keep advice light and relational; prioritize understanding and connection."
                )
            })

            # Root the conversation in a vibrant relationship with Jesus (explicit, gentle emphasis)
            messages.append({
                "role": "system",
                "content": (
                    "ROOT IN JESUS: In early turns and ongoingly, gently bring the focus back to a living relationship with Jesus as the root issue and source of change. "
                    "Use heart-level language (abide, walk with Jesus, bring this to Him) rather than institutional or duty language. "
                    "Offer one simple invitation (e.g., 'Would you like to bring this to Jesus this week—how might that look?') and, when helpful, a single short verse like John 15:5. "
                    "Keep this warm and non-pressuring for exploring/not Christian users—frame it as an invitation, not an obligation."
                )
            })

            # Faith-aware branching: query conversation metadata to tailor instructions
            faith_status = "unknown"
            asked_faith_question_meta = False
            turns_seen = 0
            try:
                from ..models.sql_models import Conversation as SQLConversation
                from ..db.base import SessionLocal
                db_meta = SessionLocal()
                try:
                    conv_row = db_meta.query(SQLConversation).filter(SQLConversation.id == conversation_id).first()
                    conv_meta = {}
                    if conv_row:
                        conv_meta = (getattr(conv_row, "metadata_json", None) or {})
                        faith_status = conv_meta.get("faith_status", "unknown") or "unknown"
                        asked_faith_question_meta = bool(conv_meta.get("asked_faith_question", False))
                        turns_seen = int(conv_meta.get("turns", 0))
                        try:
                            logger.debug(
                                "Loaded conv_meta: keys=%s jesus_decline_count=%s turns=%s",
                                list(conv_meta.keys()), conv_meta.get("jesus_decline_count"), conv_meta.get("turns")
                            )
                        except Exception:
                            pass
                finally:
                    db_meta.close()
                    try:
                        # Ensure scoped_session does not retain stale identity map across requests
                        SessionLocal.remove()  # type: ignore[name-defined]
                    except Exception:
                        pass
            except Exception:
                pass

            # Orchestrator path (feature-flagged). If it raises or disabled, we continue legacy flow.
            try:
                if getattr(settings, "ORCHESTRATION_ENABLED", False):
                    # Compute assistant/user turn indexes and last assistant text from DB
                    assistant_turns, user_turns, last_assistant_text = self._get_turn_indexes(conversation_id)
                    try:
                        logger.debug(
                            "DB derived: assistant_turns=%s user_turns=%s last_assistant_snippet=%s",
                            assistant_turns, user_turns, (last_assistant_text[:60] + ("..." if len(last_assistant_text) > 60 else ""))
                        )
                    except Exception:
                        pass
                    # Detect if last assistant turn contained an actual Jesus invite
                    invite_patterns = [
                        r"where do you sense jesus inviting",
                        r"would you like to bring this to jesus",
                        r"pray with jesus",
                        r"bring this to (him|jesus)",
                    ]
                    last_turn_had_jesus = any(re.search(p, last_assistant_text or "", re.I) for p in invite_patterns)
                    # Detect user decline/accept/ignore following last Jesus invite and compute cooldown
                    try:
                        jesus_decline_count = int((conv_meta or {}).get("jesus_decline_count", 0))  # type: ignore[name-defined]
                    except Exception:
                        jesus_decline_count = 0
                    declined_jesus_until_turn_local = None
                    try:
                        djut_v = (conv_meta or {}).get("declined_jesus_until_turn")  # type: ignore[name-defined]
                        if isinstance(djut_v, int):
                            declined_jesus_until_turn_local = djut_v
                        elif isinstance(djut_v, str) and djut_v.isdigit():
                            declined_jesus_until_turn_local = int(djut_v)
                    except Exception:
                        declined_jesus_until_turn_local = None
                    decline_detected = False
                    ignore_detected = False
                    if last_turn_had_jesus:
                        lm_curr = (message or "").lower()
                        decline_patterns = [
                            r"\bno\b",
                            r"\bno thanks\b",
                            r"\bnot (?:now|really|interested|comfortable)\b",
                            r"\brather not\b",
                            r"\bdon't want\b|\bdo not want\b",
                            r"\bstop\b",
                            r"\bplease don't\b|\bplease do not\b",
                        ]
                        accept_patterns = [
                            r"\byes\b",
                            r"\bok\b|\bokay\b|\bsure\b",
                            r"\blet's\b|\blets\b",
                            r"\bi will\b|\bi'll\b",
                        ]
                        try:
                            decline_detected = any(re.search(p, lm_curr, re.I) for p in decline_patterns)
                            accepted = any(re.search(p, lm_curr, re.I) for p in accept_patterns)
                            if accepted:
                                jesus_decline_count = 0
                            elif not decline_detected:
                                if not re.search(r"\bjesus\b", lm_curr, re.I):
                                    ignore_detected = True
                        except Exception:
                            decline_detected = False
                            ignore_detected = False
                        if decline_detected or ignore_detected:
                            try:
                                jesus_decline_count = int(jesus_decline_count) + 1
                            except Exception:
                                jesus_decline_count = 1
                            try:
                                logger.debug("Incremented jesus_decline_count to %s (assistant_turns=%s)", jesus_decline_count, assistant_turns)
                            except Exception:
                                pass
                            if jesus_decline_count >= 2:
                                # Suppress invites for next 6 assistant turns (exclusive)
                                suggested_until = int(assistant_turns) + 6
                                if declined_jesus_until_turn_local is None or suggested_until > int(declined_jesus_until_turn_local):
                                    declined_jesus_until_turn_local = suggested_until
                                try:
                                    logger.debug("Computed cooldown declined_jesus_until_turn_local=%s", declined_jesus_until_turn_local)
                                except Exception:
                                    pass
                    # Intake completion from nested intake metadata
                    try:
                        intake_completed = bool(IntakeState.from_meta(conv_meta).is_complete())  # type: ignore[name-defined]
                    except Exception:
                        intake_completed = bool((conv_meta or {}).get("intake_completed", False))  # fallback for legacy
                    # Jesus-invite cadence memory from conversation metadata
                    last_invite_turn = None
                    try:
                        liv = (conv_meta or {}).get("last_jesus_invite_turn")  # type: ignore[name-defined]
                        if isinstance(liv, int):
                            last_invite_turn = liv
                        elif isinstance(liv, str) and liv.isdigit():
                            last_invite_turn = int(liv)
                    except Exception:
                        pass
                    # Limit history window: keep first system message (if any) + last 8 turns (16 msgs)
                    # Always build history from DB: system + last 8 turns
                    history_for_model: List[Dict[str, str]] = self._get_history_for_model(conversation_id, max_turns=8)
                    history_for_model.append({"role": "user", "content": message})

                    orchestrator = Orchestrator()
                    result = orchestrator.run(
                        TurnState(
                            conversation_id=conversation_id,
                            turn_index=assistant_turns,
                            intake_completed=intake_completed,
                            last_turn_had_jesus=last_turn_had_jesus,
                            last_jesus_invite_turn=last_invite_turn,
                            declined_jesus_until_turn=declined_jesus_until_turn_local,
                            last_books=[],
                            user_message=message,
                            history_for_model=history_for_model,
                        )
                    )
                    assistant_message_o = (result or {}).get("content", "")
                    metadata_o = (result or {}).get("metadata", {})
                    if (assistant_message_o or "").strip():
                        try:
                            metadata_o = normalize_meta(metadata_o or {})
                        except Exception:
                            # Be resilient if normalizer errors
                            metadata_o = (metadata_o or {})
                        try:
                            logger.debug(
                                "Cadence vars before persist: assistant_turns=%s last_turn_had_jesus=%s decline_detected=%s ignore_detected=%s jesus_decline_count=%s declined_jesus_until_turn_local=%s",
                                assistant_turns, last_turn_had_jesus, decline_detected, ignore_detected, jesus_decline_count, declined_jesus_until_turn_local,
                            )
                        except Exception:
                            pass
                        assistant_msg = await self.add_message(
                            conversation_id=conversation_id,
                            user_id="assistant",
                            content=assistant_message_o,
                            role=MessageRole.ASSISTANT,
                            message_type=MessageType.TEXT,
                            metadata=metadata_o,
                        )
                        # Persist cadence memory and turn counter on the conversation
                        try:
                            meta_updates: Dict[str, Any] = {}
                            # increment a simple assistant-turn counter stored in metadata
                            try:
                                meta_updates["turns"] = int(turns_seen) + 1  # type: ignore[name-defined]
                            except Exception:
                                pass
                            if bool(metadata_o.get("rooted_in_jesus_emphasis")):
                                meta_updates["last_jesus_invite_turn"] = int(assistant_turns)
                            # Persist decline counters/cooldown if we computed them
                            try:
                                if last_turn_had_jesus and (decline_detected or ignore_detected):
                                    meta_updates["jesus_decline_count"] = int(jesus_decline_count)
                                if declined_jesus_until_turn_local is not None:
                                    meta_updates["declined_jesus_until_turn"] = int(declined_jesus_until_turn_local)
                            except Exception:
                                pass
                            try:
                                logger.debug("Persisting conversation meta updates: %s", meta_updates)
                            except Exception:
                                pass
                            if meta_updates:
                                await self.update_conversation(
                                    conversation_id=conversation_id,
                                    user_id=user_id,
                                    metadata=meta_updates,
                                )
                                try:
                                    logger.debug("update_conversation committed for %s", conversation_id)
                                except Exception:
                                    pass
                        except Exception:
                            pass
                        return assistant_msg
            except Exception as _orch_e:
                logger.warning("Orchestrator path failed or not configured, falling back: %s", _orch_e)
                # Capture fallback reason for legacy path observability
                orch_failed_reason = "plan_validation_failed" if "plan_validation_failed" in str(_orch_e) else "orchestrator_failed"
                orch_planner_retries = 1 if orch_failed_reason == "plan_validation_failed" else 0

            # Ephemeral parsing of current user message for marriage facts (used for this turn's prompt only)
            # These will also be persisted later when updating conversation metadata.
            try:
                ephemeral_years: Optional[int] = None
                ephemeral_have_children: Optional[bool] = None
                ephemeral_children_count: Optional[int] = None
                ephemeral_prior_counseling: Optional[bool] = None

                lm_ep = (message or "").lower()

                # Years married patterns (e.g., "married 10 years", "for 3 yrs", "been married 1 year")
                years_patterns = [
                    r"\bmarried\s+(?:for\s+)?(\d{1,2})\s*(?:years|yrs|yr|year)s?\b",
                    r"\b(\d{1,2})\s*(?:years|yrs|yr|year)s?\s+(?:of\s+)?marriage\b",
                    r"\bfor\s+(\d{1,2})\s*(?:years|yrs|yr|year)s?\b.*\bmarried\b",
                ]
                for pat in years_patterns:
                    m = re.search(pat, lm_ep)
                    if m:
                        try:
                            ephemeral_years = int(m.group(1))
                            break
                        except Exception:
                            pass
                # Months (treat <1 year as 0 years for stage mapping)
                if ephemeral_years is None:
                    m_month = re.search(r"\bmarried\s+(?:for\s+)?(\d{1,2})\s*(?:months|mos|mo)\b", lm_ep)
                    if m_month:
                        ephemeral_years = 0

                # Children detection
                if re.search(r"\bno\s+(kids|children)\b|\bwithout\s+(kids|children)\b|\bno children yet\b", lm_ep):
                    ephemeral_have_children = False
                    ephemeral_children_count = 0
                else:
                    m_kids = re.search(r"\b(\d{1,2})\s*(kids|children)\b", lm_ep)
                    if m_kids:
                        try:
                            ephemeral_children_count = int(m_kids.group(1))
                            ephemeral_have_children = True
                        except Exception:
                            pass
                    elif re.search(r"\b(kids|children)\b|\bexpecting\b|\bpregnant\b", lm_ep):
                        ephemeral_have_children = True

                # Prior counseling detection
                if re.search(r"\b(counseling|counselling|counselor|counsellor|therapy|therapist)\b", lm_ep):
                    neg = re.search(r"\b(never|no|haven't|havent|didn't|didnt|not)\b.{0,12}\b(counsel|therapy|counseling)\b", lm_ep)
                    ephemeral_prior_counseling = False if neg else True

                # Prefer existing metadata when present, otherwise use ephemeral for prompt conditioning
                meta_years = None
                meta_have_children = None
                meta_children_count = None
                meta_prior_counseling = None
                try:
                    meta_years = (conv_meta or {}).get("marriage_years")  # type: ignore[name-defined]
                    meta_have_children = (conv_meta or {}).get("have_children")  # type: ignore[name-defined]
                    meta_children_count = (conv_meta or {}).get("children_count")  # type: ignore[name-defined]
                    meta_prior_counseling = (conv_meta or {}).get("prior_counseling")  # type: ignore[name-defined]
                except Exception:
                    pass

                context_years = meta_years if meta_years is not None else ephemeral_years
                context_have_children = meta_have_children if meta_have_children is not None else ephemeral_have_children
                context_children_count = meta_children_count if meta_children_count is not None else ephemeral_children_count
                context_prior_counseling = meta_prior_counseling if meta_prior_counseling is not None else ephemeral_prior_counseling

                # Stage mapping
                context_stage = None
                if isinstance(context_years, int):
                    if context_years <= 2:
                        context_stage = "newly_married"
                    elif context_years <= 10:
                        context_stage = "mid"
                    else:
                        context_stage = "long_term"

                # Prepare a concise MARRIAGE CONTEXT line if we have any facts
                marriage_context_parts: List[str] = []
                if isinstance(context_years, int):
                    stage_hint = f" ({'newly married' if context_stage=='newly_married' else 'mid' if context_stage=='mid' else 'long-term'})" if context_stage else ""
                    marriage_context_parts.append(f"Years married: {context_years}{stage_hint}")
                if isinstance(context_have_children, bool):
                    if context_have_children:
                        if isinstance(context_children_count, int):
                            marriage_context_parts.append(f"Children: {context_children_count}")
                        else:
                            marriage_context_parts.append("Children: yes")
                    else:
                        marriage_context_parts.append("Children: none")
                if isinstance(context_prior_counseling, bool):
                    marriage_context_parts.append(f"Prior counseling: {'yes' if context_prior_counseling else 'no'}")

                if marriage_context_parts:
                    messages.append({
                        "role": "system",
                        "content": "MARRIAGE CONTEXT: " + "; ".join(marriage_context_parts)
                    })
            except Exception:
                # Do not fail generation if heuristics error
                pass

            if getattr(self.settings, "PASTORAL_FAITH_BRANCHING", True):
                ask_window = turns_seen < int(getattr(settings, "FAITH_QUESTION_TURN_LIMIT", 2))
                should_ask_faith = (faith_status == "unknown") and (not asked_faith_question_meta) and ask_window
                messages.append({
                    "role": "system",
                    "content": (
                        "FAITH-AWARE BRANCHING: If the person's faith is unknown and it fits naturally, ask once in early turns: "
                        "'Are you a follower of Jesus, or are you exploring?' If they answer, adapt tone accordingly. "
                        "If they are Christian: invite anchoring in identity in Christ, gentle Scripture (optional), and encourage connection with a local church or trusted believer. "
                        "If they are exploring/not Christian: offer wisdom from Scripture as invitation, never pressure; keep language gentle and respectful. "
                        "If depression or mental-health concerns are present, encourage professional support and safety gently, without clinical directives. "
                        f"Only ask the faith question if appropriate and not yet asked: {'YES' if should_ask_faith else 'NO'}. "
                        "When using Scripture, use at most one short verse when clearly helpful; never stack multiple verses or overload citations."
                    )
                })
                logger.info(f"Faith-aware branching: should_ask_faith={should_ask_faith}, faith_status={faith_status}, turns_seen={turns_seen}")

            # Identity in Christ priority (after faith-aware branching)
            if getattr(settings, "IDENTITY_IN_CHRIST_PRIORITY", True):
                try:
                    citations = list(getattr(settings, "IDENTITY_VERSE_CITATIONS", []))
                except Exception:
                    citations = []
                citations_str = "; ".join(citations) if citations else "2 Corinthians 5:17; Galatians 2:20; Romans 8:38-39; Ephesians 3:17-19; 1 John 3:1"
                messages.append({
                    "role": "system",
                    "content": (
                        "IDENTITY-IN-CHRIST PRIORITY: For Christians, gently center identity in Christ as the primary foundation for change in marriage—being God's beloved child, transformed by Jesus and the Holy Spirit. "
                        "Keep Scripture optional and natural with a short citation when it truly helps. For exploring/not Christian users, present identity-in-Christ as a hopeful invitation without pressure. "
                        "Prefer concise, heart-level language (4–8 short sentences) to allow brief root-cause exploration, and end with exactly one open, non-leading question (compound is okay). "
                        f"Helpful identity citations (choose at most one when fitting): {citations_str}."
                    )
                })
                # Root-cause diagnostic emphasis for Christians
                messages.append({
                    "role": "system",
                    "content": (
                        "ROOT-CAUSE DIAGNOSIS: When the user is Christian or open to Christian framing, briefly help them surface underlying drivers before proposing steps—beliefs/expectations, fears/wounds, habits/patterns, communication loops. "
                        "Structure early turns as: Reflect (1–2 short sentences), Name a gentle pattern you hear (1 sentence), Invite root-cause reflection (1 sentence), then ask exactly one open, non-leading question. "
                        "Keep Scripture optional and at most one short verse when clearly helpful—avoid verse-dumps."
                    )
                })

            # Normalize user content early for downstream heuristics
            lower_msg = (message or "").lower()
            # Book attribution tracking (populated when topic rules inject book cues)
            book_pretty_list: List[str] = []
            book_pretty_to_cue: Dict[str, str] = {}
            # Store a per-book memorable quote for richer attribution (text + attribution/author)
            book_pretty_to_quote: Dict[str, Dict[str, str]] = {}
            book_priority_applied: bool = False

            # If strict pastoral mode, instruct intake-first behavior
            if getattr(settings, "PASTORAL_MODE_STRICT", False):
                intake_general = (
                    "Begin warmly. Thank them for sharing. If they express pain or struggle, acknowledge it briefly with empathy. "
                    "Ask 2–5 short, compassionate clarifying questions to understand the person's context before advising. "
                    "Gospel-first: briefly anchor in the good news of Jesus before or alongside practical steps; weave one concise Scripture naturally (e.g., Romans 8:1, Psalm 51) when relevant. "
                    "Always provide one concrete 'do this today' step, then 1–3 next steps. "
                    "If the user expresses desire for prayer or you discern it would bless them, OFFER to forward a short request to a praying partner (human) with explicit CONSENT; confirm a brief summary in the user's words and their contact preference. "
                    "If there are safety risks (abuse, self-harm, harm to others), ASK which city/region/country they are in so a human can route local help; avoid direct advice in crisis. "
                    "Tone: Reflect + Affirm + Open Questions + Summarize; ask permission before offering steps; keep a gentle, non-judgmental posture. "
                    "If topic rules are provided in system messages (e.g., marriage), draw explicitly from their principles and Scriptures. "
                    "Faith branching: if the user is Christian, lean on Scripture and invite trusted believers and church community; if not Christian, present Scripture as wisdom with a gentle invitation, never pressure."
                )

                # Marriage-first specialization: always treat topic as marriage
                intake_topic = (
                    "This conversation is focused on marriage. Ask succinct questions such as: "
                    "'Are you a husband or a wife?', 'How long have you been married?', 'What is the current state of the relationship?', "
                    "'Any safety concerns (abuse)?', 'Have you sought counseling before?', 'What is your and your spouse's faith background?'. "
                    "Do not give advice until after the user answers. If the user declines to share, offer gentle encouragement from Scripture and invite a conversation with a human pastor."
                )

                # Greeting-mode gate: for first-message greetings, keep it brief and invitational
                is_new_convo = not bool(message_history)
                lower_stripped = lower_msg.strip()
                greeting_terms = [
                    "hi", "hello", "hey", "yo", "good morning", "good afternoon", "good evening",
                    "shalom", "greetings"
                ]
                is_greeting = is_new_convo and any(
                    lower_stripped == t or lower_stripped.startswith(t + " ") for t in greeting_terms
                )

                if is_greeting:
                    messages.append({
                        "role": "system",
                        "content": (
                            "GREETING MODE: If the user's first message is only a greeting with no context, "
                            "respond briefly and warmly (1–2 short sentences), avoid implying heaviness, and ask one open, marriage-oriented question "
                            "to invite sharing (e.g., 'What would you like help with in your marriage right now?'). Do not list resources at this point."
                        ),
                    })
                else:
                    messages.append({
                        "role": "system",
                        "content": f"INTAKE INSTRUCTION: {intake_general} {intake_topic}",
                    })

            # Inject topic rules and specific protocols BEFORE history/user so the model conditions on them
            try:
                marriage_triggers = [
                    "marriage", "married", "husband", "wife", "spouse", "divorce", "separation", "affair",
                    "porn", "pornography", "accountability", "filter", "filters", "covenant eyes", "lust",
                    "integrity", "sexual integrity", "purity"
                ]
                r = self.topic_rules.get("marriage")
                if r:
                    summary_parts = []
                    iq = r.get("intake_questions", [])
                    if iq:
                        summary_parts.append("Ask these first: " + "; ".join(iq[:6]))
                    gates = r.get("gates", [])
                    if gates:
                        summary_parts.append("Do not advise until gates pass: " + "; ".join(gates[:4]))
                    adv = r.get("advice_blueprint", [])
                    if adv:
                        summary_parts.append("When advising, follow: " + "; ".join(adv[:6]))
                    tone = r.get("tone", {})
                    if isinstance(tone, dict) and tone.get("principles"):
                        summary_parts.append("Tone: " + ", ".join(tone.get("principles")[:5]))
                    core = r.get("core_commitments", [])
                    if isinstance(core, list) and core:
                        summary_parts.append("Core commitments: " + "; ".join(core[:5]))
                    style = r.get("style", {})
                    if isinstance(style, dict) and style.get("guidelines"):
                        summary_parts.append("Style: " + ", ".join(style.get("guidelines")[:3]))

                    # Book insights: surface up to 5 named sources with cues, diagnostics, themes, and a short quote
                    sources = r.get("book_sources", {})
                    if isinstance(sources, dict) and sources:
                        # Prioritize books by detected topic
                        ordered_items = list(sources.items())
                        porn_hit = any(k in lower_msg for k in ["porn", "pornography", "lust"])  # reuse
                        if porn_hit:
                            priority = [
                                "sacred_marriage",  # holiness and transformation
                                "from_this_day_forward",  # purity and daily steps
                                "the_meaning_of_marriage",  # gospel/covenant frame
                            ]
                            ordered_items = sorted(
                                sources.items(),
                                key=lambda kv: (kv[0] not in priority, priority.index(kv[0]) if kv[0] in priority else 999)
                            )
                            book_priority_applied = True

                        book_cues: List[str] = []
                        diag_cues: List[str] = []
                        theme_cues: List[str] = []
                        quote_cues: List[str] = []
                        for name, meta in ordered_items[:5]:
                            pretty = name.replace("_", " ").title()
                            cue = None
                            citation = None
                            if isinstance(meta, dict):
                                if meta.get("key_principles"):
                                    cue = meta["key_principles"][0]
                                elif meta.get("principles"):
                                    cue = meta["principles"][0]
                                elif meta.get("core_convictions"):
                                    cue = meta["core_convictions"][0]
                                cits = meta.get("citations") or []
                                citation = cits[0] if cits else None
                                # pull diagnostics/themes/quotes where present
                                if meta.get("diagnostics"):
                                    diag_cues.extend(meta["diagnostics"][:1])
                                if meta.get("chapter_themes"):
                                    theme_cues.extend(meta["chapter_themes"][:1])
                                if meta.get("memorable_quotes"):
                                    q = meta["memorable_quotes"][0]
                                    if isinstance(q, dict) and q.get("text"):
                                        quote_cues.append(f"\"{q['text']}\" — {q.get('attribution','')}")
                                        # Save the first memorable quote per book for richer attribution later
                                        book_pretty_to_quote[pretty] = {
                                            "text": q.get("text", ""),
                                            "attribution": q.get("attribution", ""),
                                        }
                            # Track for later attribution enforcement
                            book_pretty_list.append(pretty)
                            if cue:
                                book_pretty_to_cue[pretty] = cue
                            bits = [pretty]
                            if citation:
                                bits.append(f"({citation})")
                            if cue:
                                bits.append(f": {cue}")
                            book_cues.append(" ".join(bits))
                        if book_cues:
                            summary_parts.append("Books: " + " | ".join(book_cues))
                            if theme_cues:
                                summary_parts.append("Themes: " + "; ".join(theme_cues[:3]))
                            if diag_cues:
                                summary_parts.append("Diagnostics: " + " / ".join(diag_cues[:3]))
                            if quote_cues:
                                summary_parts.append("Quote: " + quote_cues[0])
                            summary_parts.append(
                                "After initial intake and safety check, when moving into practical counsel or when the user asks for guidance/resources, explicitly attribute 1 insight to a named book (briefly). Keep it short and relevant."
                            )

                    # Gentle guidance on scripture and actions (friend-like tone)
                    summary_parts.append(
                        "Scripture is optional; include at most one verse only when it clearly serves the moment, cite simply (e.g., John 15:5). "
                        "Avoid prescriptive action steps unless the user asks."
                    )

                    if summary_parts:
                        messages.append({
                            "role": "system",
                            "content": "TOPIC RULES (marriage): " + " | ".join(summary_parts)
                        })

                    # Pornography-specific protocol when detected
                    porn_hit = any(k in lower_msg for k in ["porn", "pornography", "lust"])
                    proto = r.get("protocols", {}).get("pornography_or_sexual_sin") if r else None
                    if porn_hit and isinstance(proto, dict):
                        verses = proto.get("anchor_in_scripture", {}).get("verses", [])
                        verse_hint = verses[0] if verses else "Romans 8:1"
                        messages.append({
                            "role": "system",
                            "content": (
                                "PROTOCOL (pornography/sexual sin): Honour courage; name the sin with grace + truth; "
                                f"weave one Scripture (e.g., {verse_hint}); first steps: confession to a trusted brother, "
                                "install accountability software/filters today, pray Psalm 51 daily; rebuild trust with transparency and small weekly actions; "
                                "offer consent-based forwarding to praying partners."
                            ),
                        })
            except Exception:
                pass

            # Add message history if provided
            if message_history:
                messages.extend(message_history)

            # Add the new user message
            messages.append({"role": "user", "content": message})

            # Preflight: verify key works by calling list models (helps diagnose 401)
            try:
                pre_req = urllib.request.Request(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    method="GET",
                )
                with urllib.request.urlopen(pre_req) as pre_resp:
                    _ = pre_resp.read()  # ignore body
            except urllib.error.HTTPError as he_pre:
                pre_body = None
                try:
                    pre_body = he_pre.read().decode("utf-8", errors="ignore")
                except Exception:
                    pre_body = None
                logger.error(f"Preflight models GET failed: {he_pre} body={pre_body}")
                raise

            # Call OpenAI API via direct HTTPS to avoid SDK auth differences
            url = "https://api.openai.com/v1/chat/completions"
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "presence_penalty": self.presence_penalty,
                "frequency_penalty": self.frequency_penalty,
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            # Extract the assistant's response (robust parsing + observability)
            assistant_message = ""
            try:
                choice0 = (data.get("choices") or [])[0] if isinstance(data, dict) else None
                if isinstance(choice0, dict):
                    msg_obj = choice0.get("message") or {}
                    if isinstance(msg_obj, dict):
                        assistant_message = msg_obj.get("content") or ""
                    # Some providers/models may return plain "text" instead of nested message
                    if not assistant_message and "text" in choice0:
                        assistant_message = choice0.get("text") or ""
            except Exception as _e:
                logger.warning("Failed to parse assistant message: %s", _e)
            # Debug: log snippet of assistant content for diagnosing empties
            logger.warning(
                "assistant_message len=%d preview=%r",
                len(assistant_message or ""), (assistant_message or "")[:200]
            )
            if not (assistant_message or "").strip():
                # Log truncated raw response for debugging
                try:
                    logger.error(
                        "OpenAI returned empty assistant content. Raw response (truncated): %s",
                        json.dumps(data)[:500]
                    )
                except Exception:
                    logger.error("OpenAI returned empty assistant content and response could not be serialized")
                # Trigger error path to return a visible, non-empty system message
                raise RuntimeError("Empty assistant content from OpenAI")

            # Create and save the assistant's response
            asked_question = bool(re.search(r"\?", assistant_message))
            # Determine faith branching path for observability
            faith_branch = "unknown_path"
            if getattr(settings, "PASTORAL_FAITH_BRANCHING", True):
                # If assistant appears to ask a faith question this turn
                if re.search(r"are you (a )?follower of jesus|are you christian|are you a christian|exploring faith", assistant_message, re.I):
                    faith_branch = "ask_faith"
                else:
                    # infer from current known status
                    if faith_status == "christian":
                        faith_branch = "christian_path"
                    elif faith_status == "exploring":
                        faith_branch = "exploring_path"
                    elif faith_status == "not_christian":
                        faith_branch = "not_christian_path"
            # Detect identity emphasis for observability
            identity_emphasis = False
            try:
                id_patterns = [
                    r"\bidentity in christ\b",
                    r"\bchild of god\b",
                    r"\bbeloved (?:in|by) god\b",
                    r"\byour identity (?:is|in)\b",
                ]
                # Also check if a known identity citation is present
                try:
                    citations = list(getattr(settings, "IDENTITY_VERSE_CITATIONS", []))
                except Exception:
                    citations = []
                citation_hit = any(cit.lower() in assistant_message.lower() for cit in citations)
                if any(re.search(pat, assistant_message, re.I) for pat in id_patterns) or citation_hit:
                    identity_emphasis = True
            except Exception:
                identity_emphasis = False
            # Enforce at most one explicit book attribution when cues exist — only when warranted
            book_attributions: List[str] = []
            book_scrubbed: List[str] = []
            try:
                # Heuristics to decide if we should insert a book attribution now
                assistant_msgs = 0
                total_dialog_msgs = 0
                try:
                    if message_history:
                        for mh in message_history:
                            if mh.get("role") in ("assistant", "user"):
                                total_dialog_msgs += 1
                            if mh.get("role") == "assistant":
                                assistant_msgs += 1
                except Exception:
                    pass

                advice_intent = False
                try:
                    advice_patterns = [
                        r"\bwhat should i do\b",
                        r"\bwhat do i do\b",
                        r"\bany advice\b",
                        r"\bcan you (?:give|offer) advice\b",
                        r"\bwhat advice(?: can you (?:offer|give)(?: me)?)?\b",
                        r"\bdo you have advice\b",
                        r"\bany guidance\b",
                        r"\bcan you (?:give|offer) guidance\b",
                        r"\brecommend (?:a )?(?:book|resource|next steps)\b",
                        r"\bdo you have (?:a )?(?:book|resource|author)\b",
                        r"\bhow (?:do|can) i (?:handle|respond|change|stop)\b",
                        r"\bhow (?:should|can) i\b",
                        r"\bwhat can i do\b",
                        r"\bany suggestions\b",
                        r"\bany tips\b",
                        r"\bcan you help\b",
                        r"\bsteps? (?:i|we) can take\b",
                    ]
                    advice_matches = []
                    for p in advice_patterns:
                        try:
                            if re.search(p, lower_msg, re.I):
                                advice_matches.append(p)
                        except Exception:
                            continue
                    advice_intent = len(advice_matches) > 0
                except Exception:
                    advice_intent = False
                    advice_matches = []

                # Compute early intake/safety and phase gating
                early_intake_or_safety = False
                conversation_phase = "intake"
                intake_completed_meta = False
                try:
                    safety_terms = [
                        "unsafe", "abuse", "abusive", "violence", "violent", "threat", "afraid", "fear",
                        "shout", "shouts", "yell", "yells", "scream", "screams"
                    ]
                    safety_terms_matched = [t for t in safety_terms if t in lower_msg]
                    safety_hit = len(safety_terms_matched) > 0
                    # Consider first assistant reply or very early dialogue as intake
                    early_dialog = assistant_msgs < 1 or total_dialog_msgs < 4
                    intake_completed_meta = bool((conv_meta or {}).get("intake_completed", False))  # type: ignore[name-defined]
                    early_intake_or_safety = safety_hit or early_dialog or (not intake_completed_meta)
                    # Derive a coarse conversation phase for observability
                    conversation_phase = (
                        "advice" if (intake_completed_meta and not safety_hit and advice_intent) else
                        ("chat" if (intake_completed_meta and not safety_hit) else "intake")
                    )
                    # Phase gate observability
                    try:
                        logger.info(
                            "phase_gate",
                            extra={
                                "cid": conversation_id,
                                "path": "legacy",
                                "phase": conversation_phase,
                                "advice_intent": bool(advice_intent),
                                "intake_complete": bool(intake_completed_meta),
                                "topic_conf": cls_conf if 'cls_conf' in locals() else None,
                            },
                        )
                    except Exception:
                        pass
                except Exception:
                    early_intake_or_safety = True
                    safety_hit = False
                    early_dialog = True
                    intake_completed_meta = False
                    conversation_phase = "intake"

                # Classifier-based topic + confidence gate
                cls_topic = None
                cls_conf = 0.0
                try:
                    cls = classify(message or "")
                    cls_topic = (cls.get("topic") or None)
                    try:
                        cls_conf = float(cls.get("confidence", 0.0))
                    except Exception:
                        cls_conf = 0.0
                except Exception:
                    cls_topic = None
                    cls_conf = 0.0

                # STRICT GATE (classifier): intake complete, no safety, user asks for advice/resources, confidence >= 0.6
                allow_book_insertion = (
                    advice_intent and intake_completed_meta and (not safety_hit) and (cls_conf >= 0.6)
                )
                # Gate reason snapshot for observability (canonical single value)
                if allow_book_insertion:
                    gate_reason = "ok"
                else:
                    if safety_hit:
                        gate_reason = "safety_triage"
                    elif not intake_completed_meta:
                        gate_reason = "intake_incomplete"
                    elif cls_conf < 0.6:
                        gate_reason = "low_confidence"
                    else:
                        gate_reason = "intake_incomplete"
                try:
                    logger.info(
                        "books_gate",
                        extra={
                            "cid": conversation_id,
                            "path": "legacy",
                            "advice_intent": bool(advice_intent),
                            "intake_completed": bool(intake_completed_meta),
                            "safety": bool(safety_hit),
                            "phase": conversation_phase,
                            "assistant_msgs": int(assistant_msgs),
                            "total_msgs": int(total_dialog_msgs),
                            "topic": cls_topic,
                            "topic_conf": cls_conf,
                            "allow": bool(allow_book_insertion),
                            "reason": gate_reason,
                            "scrubbed": 0,
                        },
                    )
                except Exception:
                    pass

                # Initialize defaults and scrub when gated (independent of known resource list)
                book_attributions = []
                book_scrubbed = []
                book_selection_reason = None
                if not allow_book_insertion:
                    # Scrub all resource mentions when gated
                    try:
                        assistant_message, _scrubbed_now = scrub_books_if_gated(assistant_message, allow_book_insertion)
                    except Exception:
                        _scrubbed_now = []
                    book_scrubbed = list(_scrubbed_now)
                    book_selection_reason = f"gated: {gate_reason}"
                    # If scrubbing occurred under gating, append a neutral explainer line
                    try:
                        if (not allow_book_insertion) and _scrubbed_now:
                            if assistant_message and not assistant_message.endswith(('.', '!', '?', '\n')):
                                assistant_message += "\n"
                            assistant_message += "Once we’ve finished intake and I’m confident on the topic, I can suggest resources."
                    except Exception:
                        pass
                    try:
                        logger.info(
                            "books_gate",
                            extra={
                                "cid": conversation_id,
                                "path": "legacy",
                                "allow": False,
                                "reason": gate_reason,
                                "scrubbed": len(_scrubbed_now),
                                "phase": conversation_phase,
                                "topic_conf": cls_conf,
                            },
                        )
                    except Exception:
                        pass

                if book_pretty_list:
                    # Detect explicit mentions of any known book titles in the generated text (always)
                    detected_all: List[str] = []
                    for pretty in book_pretty_list:
                        try:
                            if re.search(rf"\b{re.escape(pretty)}\b", assistant_message, re.I):
                                detected_all.append(pretty)
                        except Exception:
                            continue

                    if allow_book_insertion:
                        book_selection_reason = None
                        # Determine last assistant attribution (avoid repeating)
                        last_assistant_text = None
                        try:
                            if message_history:
                                for mh in reversed(message_history):
                                    if mh.get("role") == "assistant" and mh.get("content"):
                                        last_assistant_text = mh["content"]
                                        break
                        except Exception:
                            last_assistant_text = None
                        last_book_detected = None
                        if last_assistant_text:
                            for pretty in book_pretty_list:
                                try:
                                    if re.search(rf"\b{re.escape(pretty)}\b", last_assistant_text, re.I):
                                        last_book_detected = pretty
                                        break
                                except Exception:
                                    continue

                        detected: List[str] = list(detected_all)
                        # If none detected in the model output, insert a simple, non-repeating fallback attribution
                        if not detected:
                            # Choose first non-repeating from curated list; otherwise fallback to first
                            chosen_pretty = None
                            for p in book_pretty_list:
                                # Repetition penalty: avoid last assistant attribution and last_used_book from meta
                                last_used_book_meta = None
                                try:
                                    last_used_book_meta = (conv_meta or {}).get("last_used_book")  # type: ignore[name-defined]
                                except Exception:
                                    last_used_book_meta = None
                                if p != last_book_detected and p != last_used_book_meta:
                                    chosen_pretty = p
                                    break
                            chosen_pretty = chosen_pretty or (book_pretty_list[0] if book_pretty_list else None)
                            if chosen_pretty:
                                # Insert a concise attribution sentence at the end
                                attribution_line = None
                                cue_text = book_pretty_to_cue.get(chosen_pretty, "a helpful principle for this situation")
                                # Prefer a short memorable quote with attribution when available
                                qmeta = book_pretty_to_quote.get(chosen_pretty) or {}
                                qtext = (qmeta.get("text") or "").strip()
                                qattr = (qmeta.get("attribution") or "").strip()
                                if qtext:
                                    insertion = f" From {chosen_pretty}, one helpful idea is: {cue_text}. For example: “{qtext}”"
                                    if qattr:
                                        insertion += f" — {qattr}."
                                    else:
                                        insertion += "."
                                else:
                                    insertion = f" From {chosen_pretty}, one helpful idea is: {cue_text}."
                                assistant_message = (assistant_message or "").strip()
                                if assistant_message and not assistant_message.endswith(('.', '!', '?')):
                                    assistant_message += "."
                                assistant_message = assistant_message + insertion
                                # Record attribution metadata and reason
                                try:
                                    book_attributions = [chosen_pretty]
                                    book_selection_reason = "fallback_insert"
                                    logger.info(
                                        "book_insert",
                                        extra={
                                            "cid": conversation_id,
                                            "path": "legacy",
                                            "book": chosen_pretty,
                                            "reason": book_selection_reason,
                                        },
                                    )
                                except Exception:
                                    pass
                                # Ensure we end with exactly one open, gentle, Jesus-centered question if none was asked
                                if not asked_question:
                                    assistant_message += " What part of that connects with where Jesus might be inviting you to grow together right now?"
                                    asked_question = True
                        else:
                            # Detected book(s) in model output; keep at most one attribution for this turn
                            try:
                                book_attributions = [detected[0]]
                                book_selection_reason = "detected"
                                logger.info(
                                    "book_detected",
                                    extra={
                                        "cid": conversation_id,
                                        "path": "legacy",
                                        "book": detected[0],
                                        "count": len(detected),
                                    },
                                )
                            except Exception:
                                pass
                if assistant_message and not assistant_message.endswith(('.', '!', '?')):
                    assistant_message += "."
                # rotate generic pastoral prompts to avoid repetition (no Jesus mention here)
                _variants = [
                    " What feels most important to tackle first?",
                    " What would be a small, doable next step?",
                    " What would be helpful for me to understand better?",
                ]
                # Use assistant turn index for rotation
                _assistant_turn_index = 0
                try:
                    for _mh in (message_history or []):
                        if _mh.get("role") == "assistant":
                            _assistant_turn_index += 1
                except Exception:
                    _assistant_turn_index = 0
                _idx = _assistant_turn_index % len(_variants)
                assistant_message += _variants[_idx]
                asked_question = True
            except Exception as _e:
                logger.warning("book_attribution_enforcement_error: %s", _e)

            # Replace any placeholder redactions with a neutral, helpful line (legacy compose point)
            try:
                _ph_pattern = re.compile(r"\[resource removed\]", re.I)
                _ph_count = len(_ph_pattern.findall(assistant_message or ""))
                if _ph_count:
                    assistant_message = _ph_pattern.sub("", assistant_message or "")
                    # Tidy whitespace
                    assistant_message = re.sub(r"[ \t]{2,}", " ", (assistant_message or "")).strip()
                    # Ensure the neutral explainer is present
                    if assistant_message and not assistant_message.endswith(('.', '!', '?', '\n')):
                        assistant_message += "\n"
                    assistant_message += "Once we’ve finished intake and I’m confident on the topic, I can suggest resources."
                    try:
                        logger.info(
                            "resource_placeholder_replaced",
                            extra={
                                "cid": conversation_id,
                                "path": "legacy",
                                "count": _ph_count,
                            },
                        )
                    except Exception:
                        pass
            except Exception:
                pass

            # If user asked for advice but intake is not complete, inject an explicit wrap-up prompt
            try:
                if advice_intent and not intake_completed_meta:
                    wrapup = (
                        "To give you the best next steps, can I quickly confirm a couple details: "
                        "(1) the main issue you’re facing, (2) one hope or goal for the next few weeks, and "
                        "(3) whether there are any safety concerns right now? If that’s already covered, just say “that’s enough” and I’ll move to advice."
                    )
                    assistant_message = (assistant_message or "").strip()
                    if assistant_message and not assistant_message.endswith(('.', '!', '?', '\n')):
                        assistant_message += "\n"
                    assistant_message += wrapup
                    asked_question = True
            except Exception:
                pass

            rooted_in_jesus_emphasis = bool(re.search(r"\bjesus\b", assistant_message, re.I))
            # If no explicit Jesus emphasis yet, gate any Jesus-invite with the canonical invite_gate
            from ..orchestration.graph import invite_gate
            last_assistant_text_for_jesus = None
            assistant_turn_index = 0
            last_turn_had_jesus = False
            cadence_reason = "unknown"
            allow_jesus_invite = False
            jesus_invite_variant_val = 0
            jesus_invite_added = False
            decline_detected = False
            ignore_detected = False
            try:
                # DB-derived assistant/user counts and last assistant content
                assistant_turn_index, _user_turns_ign, last_assistant_text_for_jesus = self._get_turn_indexes(conversation_id)
                # Prefer DB metadata flag from last assistant message over regex
                try:
                    from ..models.sql_models import Message as SQLMessage
                    from ..db.base import SessionLocal
                    _dbtmp = SessionLocal()
                    try:
                        last_a = (
                            _dbtmp.query(SQLMessage)
                            .filter(SQLMessage.conversation_id == conversation_id, SQLMessage.role == "assistant")
                            .order_by(SQLMessage.created_at.desc())
                            .first()
                        )
                        if last_a is not None:
                            _md = getattr(last_a, "metadata_json", None) or {}
                            if isinstance(_md.get("had_jesus_invite"), bool):
                                last_turn_had_jesus = bool(_md.get("had_jesus_invite"))
                            else:
                                # Fallback to regex detection if metadata was missing on older messages
                                invite_patterns_legacy = [
                                    r"where do you sense jesus inviting",
                                    r"would you like to bring this to jesus",
                                    r"pray with jesus",
                                    r"bring this to (him|jesus)",
                                ]
                                last_turn_had_jesus = any(
                                    re.search(p, last_assistant_text_for_jesus or "", re.I) for p in invite_patterns_legacy
                                )
                    finally:
                        _dbtmp.close()
                except Exception:
                    # Conservative fallback
                    last_turn_had_jesus = False
            except Exception:
                assistant_turn_index = 0
                last_turn_had_jesus = False

            # Read conversation metadata needed for canonical gate
            djut_val = None
            last_invite_turn = None
            jesus_decline_count = 0
            consent_known = False
            consent_val = False
            try:
                # Fresh DB read for conversation metadata
                from ..models.sql_models import Conversation as SQLConversation
                from ..db.base import SessionLocal
                db_tmp = SessionLocal()
                try:
                    conv_row = db_tmp.query(SQLConversation).filter(SQLConversation.id == conversation_id).first()
                    if conv_row:
                        _meta_ro = getattr(conv_row, "metadata_json", None) or {}
                        # Cooldown
                        djut_meta = _meta_ro.get("declined_jesus_until_turn")
                        if isinstance(djut_meta, int):
                            djut_val = djut_meta
                        elif isinstance(djut_meta, str) and djut_meta.isdigit():
                            djut_val = int(djut_meta)
                        # Last invite turn
                        liv = _meta_ro.get("last_jesus_invite_turn")
                        if isinstance(liv, int):
                            last_invite_turn = liv
                        elif isinstance(liv, str) and liv.isdigit():
                            last_invite_turn = int(liv)
                        # Decline counter
                        try:
                            jesus_decline_count = int(_meta_ro.get("jesus_decline_count", 0))
                        except Exception:
                            jesus_decline_count = 0
                        # Prayer consent
                        consent_known = bool(_meta_ro.get("prayer_consent_known", False))
                        consent_val = bool(_meta_ro.get("prayer_consent", False))
                        if not consent_known:
                            # also check nested intake
                            try:
                                intake_meta = _meta_ro.get("intake") or {}
                                if isinstance(intake_meta, dict):
                                    consent_known = bool(intake_meta.get("prayer_consent_known", False))
                            except Exception:
                                pass
                finally:
                    db_tmp.close()
                    try:
                        # Ensure scoped_session does not retain stale identity map across requests
                        SessionLocal.remove()  # type: ignore[misc]
                    except Exception:
                        pass
            except Exception:
                djut_val = djut_val if isinstance(djut_val, int) else None

            # Detect prayer consent change from current user message
            try:
                lm_curr = (message or "").lower()
                consent_yes = [
                    r"\bplease\s+pray\b",
                    r"\bpray\s+for\s+me\b",
                    r"\byes\b.*\bforward\b.*\bprayer\b",
                    r"\byou\s+can\s+forward\b.*\bprayer\b",
                ]
                consent_no = [
                    r"\bno\s+prayer\b",
                    r"\bdo\s+not\s+pray\b|don't\s+pray",
                    r"\bplease\s+don't\s+pray\b",
                ]
                if any(re.search(p, lm_curr, re.I) for p in consent_yes):
                    consent_known = True
                    consent_val = True
                elif any(re.search(p, lm_curr, re.I) for p in consent_no):
                    consent_known = True
                    consent_val = False
            except Exception:
                pass

            # Detect decline/ignore of last Jesus invite to update cooldown snapshot
            declined_until_local = djut_val if isinstance(djut_val, int) else None
            try:
                if last_turn_had_jesus:
                    decline_patterns = [
                        r"\bno\b",
                        r"\bno thanks\b",
                        r"\bnot (?:now|really|interested|comfortable)\b",
                        r"\brather not\b",
                        r"\bdon't want\b|\bdo not want\b",
                        r"\bstop\b",
                        r"\bplease don't\b|\bplease do not\b",
                    ]
                    accept_patterns = [
                        r"\byes\b",
                        r"\bok\b|\bokay\b|\bsure\b",
                        r"\blet's\b|\blets\b",
                        r"\bi will\b|\bi'll\b",
                    ]
                    try:
                        decline_detected = any(re.search(p, lm_curr, re.I) for p in decline_patterns)
                        accepted = any(re.search(p, lm_curr, re.I) for p in accept_patterns)
                        if accepted:
                            jesus_decline_count = 0
                        elif not decline_detected:
                            if not re.search(r"\bjesus\b", lm_curr, re.I):
                                ignore_detected = True
                    except Exception:
                        decline_detected = False
                        ignore_detected = False
                    if decline_detected or ignore_detected:
                        try:
                            jesus_decline_count = int(jesus_decline_count) + 1
                        except Exception:
                            jesus_decline_count = 1
                        if jesus_decline_count >= 2:
                            # Suppress invites for next 6 assistant turns (exclusive)
                            suggested_until = int(assistant_turn_index) + 6
                            if declined_until_local is None or suggested_until > int(declined_until_local):
                                declined_until_local = suggested_until
            except Exception:
                pass

            # Canonical invite gate
            try:
                _phase = locals().get("conversation_phase", None) or conversation_phase
            except Exception:
                _phase = "intake"
            try:
                allow_jesus_invite, cadence_reason = invite_gate(
                    phase=_phase,
                    advice_intent=bool(locals().get("advice_intent", False) or advice_intent),
                    intake_completed=bool(locals().get("intake_completed_meta", False) or intake_completed_meta),
                    safety_flag=bool(locals().get("safety_hit", False)),
                    assistant_turn_index=int(assistant_turn_index),
                    last_jesus_invite_turn=last_invite_turn if isinstance(last_invite_turn, int) else None,
                    declined_jesus_until_turn=declined_until_local,
                    prayer_consent_known=bool(consent_known),
                    prayer_consent=bool(consent_val),
                    jesus_invite_allowed_from_plan=True,
                )
            except Exception:
                allow_jesus_invite = False
                cadence_reason = "unknown"

            # Append invite only when allowed
            if (not rooted_in_jesus_emphasis) and allow_jesus_invite:
                if assistant_message and not assistant_message.endswith(('.', '!', '?')):
                    assistant_message += "."
                _variants2 = [
                    " Where do you sense Jesus inviting you to take one small, grace-filled step this week?",
                    " What might Jesus be leading you to try as a small next step right now?",
                    " How could you bring this to Jesus in a practical way this week?",
                ]
                _idx2 = (assistant_turn_index + 1) % len(_variants2)
                if _variants2[_idx2] not in assistant_message:
                    assistant_message += _variants2[_idx2]
                rooted_in_jesus_emphasis = True
                jesus_invite_variant_val = _idx2
                jesus_invite_added = True

            try:
                logger.info(
                    "gate",
                    extra={
                        "cid": conversation_id,
                        "path": "legacy",
                        "phase": locals().get("conversation_phase", None),
                        "advice_intent": bool(locals().get("advice_intent", False)),
                        "intake_completed": bool(locals().get("intake_completed_meta", False)),
                        "safety": bool(locals().get("safety_hit", False)),
                        "consent_known": bool(locals().get("consent_known", False)),
                        "consent": bool(locals().get("consent_val", False)),
                        "a_idx": int(assistant_turn_index),
                        "last_invite": last_invite_turn if isinstance(last_invite_turn, int) else None,
                        "until": declined_until_local,
                        "allow_jesus": bool(allow_jesus_invite),
                        "cadence_reason": cadence_reason,
                        "allow_books": bool(locals().get("allow_book_insertion", False)),
                        "gate_reason": locals().get("gate_reason", None),
                    },
                )
            except Exception:
                pass

            # Derive intake confirmation for THIS TURN (deterministic flip on explicit affirmation)
            # This is computed before building per-message metadata so the assistant message includes nested intake.completed
            try:
                # Use the raw message to avoid any upstream alterations and lowercase it here
                lm_now = ((message or "")).lower()
                confirm_patterns_now = [
                    r"\bthat's enough\b(?:[.,!]|$)",
                    r"\bthats enough\b(?:[.,!]|$)",
                    r"\bwe'?re good\b(?:[.,!]|$)",
                    r"\bready for advice\b",
                    r"\bi'?m ready for advice\b",
                    r"\bi am ready for advice\b",
                    r"\bdone with intake\b",
                    r"\bmove to advice\b",
                    r"\bgo ahead\b",
                ]
                wrap_confirm_now = any(re.search(p, lm_now, re.I) for p in confirm_patterns_now)
            except Exception:
                wrap_confirm_now = False
            try:
                # Simple substring fallback (defensive) to avoid any regex edge-cases
                if not wrap_confirm_now:
                    if (
                        ("that's enough" in lm_now)
                        or ("thats enough" in lm_now)
                        or ("ready for advice" in lm_now)
                        or ("i'm ready for advice" in lm_now)
                        or ("i am ready for advice" in lm_now)
                        or ("we're good" in lm_now)
                        or ("we are good" in lm_now)
                        or ("done with intake" in lm_now)
                        or ("move to advice" in lm_now)
                        or ("go ahead" in lm_now)
                    ):
                        wrap_confirm_now = True
                logger.warning(
                    "wrap_confirm_now",
                    extra={
                        "cid": conversation_id,
                        "path": "legacy",
                        "msg": lm_now,
                        "wrap": bool(wrap_confirm_now),
                        "msg_length": len(lm_now),
                        "contains_thats_enough": "that's enough" in lm_now,
                        "contains_ready_for_advice": "ready for advice" in lm_now,
                    },
                )
            except Exception:
                pass
            # Build an intake snapshot for message metadata
            try:
                greetings_now = ["hello", "hi", "hey", "good morning", "good afternoon", "good evening"]
                issue_named_now = bool(len(lm_now.strip()) > 12 and not any(g in lm_now for g in greetings_now))
            except Exception:
                issue_named_now = False
            try:
                intake_completed_now = bool(locals().get("intake_completed_meta", False) or wrap_confirm_now)
                # When wrap-up is confirmed, force all intake flags to True for completion
                if wrap_confirm_now:
                    intake_meta_for_msg = {
                        "issue_named": True,
                        "safety_cleared": True,
                        "goal_captured": True,
                        "prayer_consent_known": True,
                        "completed": True,
                    }
                    intake_completed_now = True
                else:
                    intake_meta_for_msg = {
                        "issue_named": bool(issue_named_now),
                        "safety_cleared": bool(not locals().get("safety_hit", False)),
                        "goal_captured": bool(locals().get("advice_intent", False)),
                        "prayer_consent_known": bool(locals().get("consent_known", False)),
                        "completed": bool(intake_completed_now),
                    }
            except Exception:
                intake_meta_for_msg = {"completed": bool(locals().get("intake_completed_meta", False) or wrap_confirm_now)}
                intake_completed_now = bool(intake_meta_for_msg.get("completed", False))
            # Defensive: if wrap confirmation detected but completed flag not set due to logic above, set it now
            if wrap_confirm_now and not bool(intake_meta_for_msg.get("completed", False)):
                intake_meta_for_msg["completed"] = True
                intake_completed_now = True
            try:
                logger.warning(
                    "intake_meta_for_msg",
                    extra={
                        "cid": conversation_id,
                        "path": "legacy",
                        "intake": intake_meta_for_msg,
                    },
                )
            except Exception:
                pass
            # Adjust allow_books and gate_reason for this message based on derived intake snapshot
            try:
                allow_books_msg = bool(
                    locals().get("advice_intent", False)
                    and bool(intake_completed_now)
                    and (not bool(locals().get("safety_hit", False)))
                    and (float(locals().get("cls_conf", 0.0)) >= 0.6)
                )
                if allow_books_msg:
                    gate_reason_msg = "ok"
                else:
                    if locals().get("safety_hit", False):
                        gate_reason_msg = "safety_triage"
                    elif not intake_completed_now:
                        gate_reason_msg = "intake_incomplete"
                    elif float(locals().get("cls_conf", 0.0)) < 0.6:
                        gate_reason_msg = "low_confidence"
                    else:
                        gate_reason_msg = "ok"
            except Exception:
                allow_books_msg = bool(locals().get("allow_book_insertion", False))
                gate_reason_msg = locals().get("gate_reason", None)

            # Build canonical metadata and normalize for observability
            _legacy_meta = {
                "model": self.model,
                "style_guide": "friend_v1",
                "asked_question": asked_question,
                "faith_branch": faith_branch,
                "rooted_in_jesus_emphasis": rooted_in_jesus_emphasis,
                "book_attributions": book_attributions,
                "scrubbed_books": book_scrubbed,
                "phase": conversation_phase,
                "advice_intent": advice_intent,
                "safety_flag_this_turn": safety_hit,
                "gate_reason": gate_reason_msg,
                "book_selection_reason": book_selection_reason,
                "jesus_invite_variant": jesus_invite_variant_val,
                # Orchestration fallback + path
                "path": "legacy",
                "fallback_reason": locals().get("orch_failed_reason", None),
                "planner_retries": locals().get("orch_planner_retries", 0),
                "allow_books": allow_books_msg,
                "allow_jesus": allow_jesus_invite,
                "cadence_reason": cadence_reason,
                # Per-message flag to mirror orchestrator for DB-derived history
                "had_jesus_invite": bool(jesus_invite_added),
                # Topic classifier signals
                "topic": locals().get("cls_topic", None),
                "topic_confidence": locals().get("cls_conf", 0.0),
                # Additional diagnostic fields retained (non-canonical)
                "identity_emphasis": identity_emphasis,
                "book_cues": book_pretty_list,
                "used_book_attribution": (book_attributions[0] if book_attributions else None),
                "book_priority_applied": book_priority_applied,
                "advice_patterns_matched": locals().get("advice_matches", []),
                "safety_terms_matched": locals().get("safety_terms_matched", []),
                "intake_completed_meta": intake_completed_now,
                "allow_book_insertion": allow_books_msg,
                # Deterministic intake snapshot for this turn
                "intake": intake_meta_for_msg,
            }
            try:
                _legacy_meta = normalize_meta(_legacy_meta)
            except Exception:
                pass

            assistant_msg = await self.add_message(
                conversation_id=conversation_id,
                user_id="assistant",  # Or use a system user ID
                content=assistant_message,
                role=MessageRole.ASSISTANT,
                message_type=MessageType.TEXT,
                metadata=_legacy_meta,
            )
            try:
                used_book_attr = (book_attributions[0] if book_attributions else "")
                logger.info(
                    "generation_ok cid=%s len=%d asked_q=%s faith_branch=%s identity_emphasis=%s book_cues=%s used_book_attr=%s",
                    conversation_id,
                    len(assistant_message or ""),
                    asked_question,
                    faith_branch,
                    identity_emphasis,
                    ", ".join(book_pretty_list) if book_pretty_list else "",
                    used_book_attr,
                )
            except Exception:
                pass
            # Update conversation metadata/state
            try:
                from ..models.sql_models import Conversation as SQLConversation
                from ..db.base import SessionLocal
                from ..policies.intake import IntakeState
                db = SessionLocal()
                try:
                    conv = db.query(SQLConversation).filter(SQLConversation.id == conversation_id).first()
                    if conv:
                        meta = getattr(conv, "metadata_json", None) or {}
                        old_meta = dict(meta)
                        # Increment turns
                        meta["turns"] = int(meta.get("turns", 0)) + 1
                        # Record last_jesus_invite_turn if we appended an invite this turn
                        if locals().get("jesus_invite_added", False):
                            try:
                                # Use DB-derived assistant turn index to match orchestrator semantics
                                meta["last_jesus_invite_turn"] = int(locals().get("assistant_turn_index", 0))
                            except Exception:
                                pass
                        # Persist consent state if known
                        try:
                            if bool(locals().get("consent_known", False)):
                                meta["prayer_consent_known"] = True
                                meta["prayer_consent"] = bool(locals().get("consent_val", False))
                                # Also reflect in intake nested state if present
                                if isinstance(meta.get("intake"), dict):
                                    meta["intake"]["prayer_consent_known"] = True
                        except Exception:
                            pass
                        # Lowercased user message for heuristics
                        lm = (message or "").lower()
                        try:
                            # Marriage
                            years_val: Optional[int] = None
                            for pat in [
                                r"\bmarried\s+(?:for\s+)?(\d{1,2})\s*(?:years|yrs|yr|year)s?\b",
                                r"\b(\d{1,2})\s*(?:years|yrs|yr|year)s?\s+(?:of\s+)?marriage\b",
                                r"\bfor\s+(\d{1,2})\s*(?:years|yrs|yr|year)s?\b.*\bmarried\b",
                            ]:
                                m = re.search(pat, lm)
                                if m:
                                    try:
                                        years_val = int(m.group(1))
                                        break
                                    except Exception:
                                        pass
                            if years_val is None:
                                if re.search(r"\bmarried\s+(?:for\s+)?(\d{1,2})\s*(?:months|mos|mo)\b", lm):
                                    years_val = 0
                            if years_val is not None:
                                meta["marriage_years"] = years_val
                                # Stage mapping
                                if years_val <= 2:
                                    meta["marriage_stage"] = "newly_married"
                                elif years_val <= 10:
                                    meta["marriage_stage"] = "mid"
                                else:
                                    meta["marriage_stage"] = "long_term"

                            # Children
                            if re.search(r"\bno\s+(kids|children)\b|\bwithout\s+(kids|children)\b|\bno children yet\b", lm):
                                meta["have_children"] = False
                                meta["children_count"] = 0
                            else:
                                m_k = re.search(r"\b(\d{1,2})\s*(kids|children)\b", lm)
                                if m_k:
                                    try:
                                        meta["children_count"] = int(m_k.group(1))
                                        meta["have_children"] = True
                                    except Exception:
                                        pass
                                elif re.search(r"\b(kids|children)\b|\bexpecting\b|\bpregnant\b", lm):
                                    meta["have_children"] = True

                            # Prior counseling
                            if re.search(r"\b(counseling|counselling|counselor|counsellor|therapy|therapist)\b", lm):
                                neg = re.search(r"\b(never|no|haven't|havent|didn't|didnt|not)\b.{0,12}\b(counsel|therapy|counseling)\b", lm)
                                meta["prior_counseling"] = False if neg else True
                        except Exception:
                            pass
                        consent_patterns = [
                            r"\bplease\s+pray\b",
                            r"\bpray\s+for\s+me\b",
                            r"\byes\b.*\bforward\b.*\bprayer\b",
                            r"\byou\s+can\s+forward\b.*\bprayer\b",
                        ]
                        if any(re.search(p, lm) for p in consent_patterns):
                            meta["consent_for_prayer"] = True
                        else:
                            meta["consent_for_prayer"] = bool(meta.get("consent_for_prayer", False))
                        # Detect last_intent from user message
                        intent = None
                        if any(k in lm for k in ["porn", "pornography", "lust", "accountability", "filter", "filters"]):
                            intent = "sexual_integrity"
                        elif any(k in lm for k in ["divorce", "separation", "separated"]):
                            intent = "divorce_or_separation"
                        elif any(k in lm for k in ["trust", "betrayal", "affair", "adultery"]):
                            intent = "rebuilding_trust"
                        elif any(k in lm for k in ["argue", "conflict", "fight", "communication"]):
                            intent = "communication_conflict"
                        elif any(k in lm for k in ["pray", "prayer"]):
                            intent = "prayer_support"
                        elif any(k in lm for k in ["hello", "hi", "hey", "good morning", "good afternoon", "good evening"]):
                            intent = "greeting"
                        if intent:
                            meta["last_intent"] = intent
                        # Faith-aware metadata
                        if getattr(settings, "PASTORAL_FAITH_BRANCHING", True):
                            # infer faith_status from user/assistant content
                            # User message signals
                            if re.search(r"\b(i am|i'm)\s+(a\s+)?(christian|believer|follower of jesus)\b", lm):
                                meta["faith_status"] = "christian"
                            elif re.search(r"\b(i am|i'm)\s+(not\s+)?(christian|religious)\b", lm) or re.search(r"\b(agnostic|atheist)\b", lm):
                                meta["faith_status"] = "not_christian"
                            elif re.search(r"\b(i am|i'm)\s+(just\s+)?exploring( faith)?\b", lm) or "exploring faith" in lm:
                                meta["faith_status"] = "exploring"
                            # Assistant faith question detection (to avoid repeat)
                            if re.search(r"are you (a )?follower of jesus|are you christian|are you a christian|exploring faith", assistant_message, re.I):
                                meta["asked_faith_question"] = True
                            # Local church detection
                            if re.search(r"\b(church|small group|community group|pastor)\b", lm):
                                neg = re.search(r"\b(no(t)?|don'?t|without|haven't|not in a)\b", lm)
                                meta["has_local_church"] = False if neg else True
                        # Identity encouragement counter
                        if getattr(self.settings, "IDENTITY_IN_CHRIST_PRIORITY", True):
                            if identity_emphasis:
                                try:
                                    meta["identity_encouragement_count"] = int(meta.get("identity_encouragement_count", 0)) + 1
                                except Exception:
                                    meta["identity_encouragement_count"] = 1
                        # Conversation phase and gating counters
                        try:
                            # Phase from this turn
                            meta["conversation_phase"] = locals().get("conversation_phase", meta.get("conversation_phase", "intake"))
                            # Advice request counter (user intent)
                            if locals().get("advice_intent", False):
                                meta["advice_request_count"] = int(meta.get("advice_request_count", 0)) + 1
                            # Persist intake completion deterministically when affirmed this turn
                            try:
                                # Check for wrap-up confirmation from early detection
                                wrap_detected = bool(locals().get("wrap_confirm_now", False))
                                intake_complete = bool(locals().get("intake_completed_now", False))
                                
                                if wrap_detected or intake_complete:
                                    meta["intake_completed"] = True
                                    if not isinstance(meta.get("intake"), dict):
                                        meta["intake"] = {}
                                    # Force ALL intake flags to True for definitive completion
                                    meta["intake"]["completed"] = True
                                    meta["intake"]["issue_named"] = True
                                    meta["intake"]["safety_cleared"] = True
                                    meta["intake"]["goal_captured"] = True
                                    meta["intake"]["prayer_consent_known"] = True  # Critical for IntakeState.is_complete()
                                    try:
                                        logger.info(
                                            "intake_persist",
                                            extra={
                                                "cid": conversation_id,
                                                "path": "legacy",
                                                "completed": True,
                                                "affirmed": wrap_detected,
                                                "wrap_confirm_now": wrap_detected,
                                                "intake_completed_now": intake_complete,
                                                "final_intake_meta": meta.get("intake", {}),
                                            },
                                        )
                                    except Exception:
                                        pass
                            except Exception:
                                pass
                            # Book attribution counter (assistant usage)
                            if locals().get("book_attributions"):
                                try:
                                    meta["book_attribution_count"] = int(meta.get("book_attribution_count", 0)) + len(locals().get("book_attributions") or [])
                                except Exception:
                                    meta["book_attribution_count"] = int(meta.get("book_attribution_count", 0)) + 1
                            # Last used book and gating snapshot
                            if locals().get("allow_book_insertion", False):
                                meta["last_used_book"] = (locals().get("book_attributions") or [None])[0]
                            meta["allow_book_insertion_last"] = bool(locals().get("allow_book_insertion", False))
                            meta["safety_flag_last"] = bool(locals().get("safety_hit", False))
                            # Persist decline counters/cooldown in legacy path using DB-derived detection
                            try:
                                # Compute from DB for this conversation
                                from ..models.sql_models import Message as SQLMessage
                                a_turns = 0
                                last_a_txt = ""
                                try:
                                    rows2 = (
                                        db.query(SQLMessage)
                                        .filter(SQLMessage.conversation_id == conversation_id)
                                        .order_by(SQLMessage.created_at.asc())
                                        .all()
                                    )
                                    for r2 in rows2:
                                        if r2.role == "assistant":
                                            a_turns += 1
                                            last_a_txt = r2.content or last_a_txt
                                except Exception:
                                    pass
                                invite_patterns = [
                                    r"where do you sense jesus inviting",
                                    r"would you like to bring this to jesus",
                                    r"pray with jesus",
                                    r"bring this to (him|jesus)",
                                ]
                                last_turn_had_jesus_l = any(re.search(p, last_a_txt or "", re.I) for p in invite_patterns)
                                lm_curr_l = (message or "").lower()
                                decline_patterns_l = [
                                    r"\bno\b",
                                    r"\bno thanks\b",
                                    r"\bnot (?:now|really|interested|comfortable)\b",
                                    r"\brather not\b",
                                    r"\bdon't want\b|\bdo not want\b",
                                    r"\bstop\b",
                                    r"\bplease don't\b|\bplease do not\b",
                                ]
                                accept_patterns_l = [
                                    r"\byes\b",
                                    r"\bok\b|\bokay\b|\bsure\b",
                                    r"\blet's\b|\blets\b",
                                    r"\bi will\b|\bi'll\b",
                                ]
                                try:
                                    decline_detected_l = any(re.search(p, lm_curr_l, re.I) for p in decline_patterns_l)
                                    accepted_l = any(re.search(p, lm_curr_l, re.I) for p in accept_patterns_l)
                                except Exception:
                                    decline_detected_l = False
                                    accepted_l = False
                                ignore_detected_l = False
                                if last_turn_had_jesus_l and not decline_detected_l and not accepted_l:
                                    if not re.search(r"\bjesus\b", lm_curr_l, re.I):
                                        ignore_detected_l = True
                                # Load existing counters
                                try:
                                    jdc = int(meta.get("jesus_decline_count", 0))
                                except Exception:
                                    jdc = 0
                                djut = meta.get("declined_jesus_until_turn")
                                if accepted_l:
                                    jdc = 0
                                elif last_turn_had_jesus_l and (decline_detected_l or ignore_detected_l):
                                    jdc = jdc + 1
                                    if jdc >= 2:
                                        suggested_until_l = int(a_turns) + 6
                                        if not isinstance(djut, int) or suggested_until_l > int(djut):
                                            djut = suggested_until_l
                                meta["jesus_decline_count"] = int(jdc)
                                if isinstance(djut, int):
                                    meta["declined_jesus_until_turn"] = int(djut)
                            except Exception:
                                pass
                        except Exception:
                            pass
                        # Detect last scripture used from assistant message
                        am = assistant_message
                        scripture_match = re.search(r"\b(?:[1-3]\s*)?[A-Za-z]+\s+\d+:\d+(?:-\d+)?\b", am)
                        if scripture_match:
                            meta["last_scripture_used"] = scripture_match.group(0)
                        # Heuristic trust rebuild stage
                        am_l = am.lower()
                        if any(k in am_l for k in ["transparency", "weekly actions", "accountability"]):
                            meta["trust_rebuild_stage"] = "early_repair"
                        # Intake checklist: derive and persist completion using IntakeState
                        try:
                            intake_state = IntakeState.from_meta(meta)
                            # Check if wrap-up was confirmed this turn
                            wrap_confirmed_this_turn = bool(locals().get("wrap_confirm_now", False))
                            
                            if wrap_confirmed_this_turn:
                                # Force all intake flags to True when wrap-up is confirmed
                                intake_state.issue_named = True
                                intake_state.safety_cleared = True
                                intake_state.goal_captured = True
                                intake_state.prayer_consent_known = True
                            else:
                                # Update fields based on this turn
                                intake_state.prayer_consent_known = bool(locals().get("consent_known", False) or meta.get("prayer_consent_known", False))
                                # Consider issue named if user shared non-trivial content not just greeting
                                greetings = ["hello", "hi", "hey", "good morning", "good afternoon", "good evening"]
                                intake_state.issue_named = bool(intake_state.issue_named or (len(lm.strip()) > 12 and not any(g in lm for g in greetings)))
                                # Safety cleared when no safety flag this turn
                                intake_state.safety_cleared = bool(intake_state.safety_cleared or not bool(locals().get("safety_hit", False)))
                                # Goal captured if advice intent detected
                                intake_state.goal_captured = bool(intake_state.goal_captured or bool(locals().get("advice_intent", False)))
                            # Explicit intake wrap-up confirmation (user says we're good to proceed)
                            try:
                                lm_l = (lm or "").lower()
                                confirm_patterns = [
                                    r"\bthat's enough\b",
                                    r"\bthats enough\b",
                                    r"\bwe'?re good\b",
                                    r"\bready for advice\b",
                                    r"\bdone with intake\b",
                                    r"\bmove to advice\b",
                                    r"\bgo ahead\b",
                                ]
                                wrap_confirm = any(re.search(p, lm_l, re.I) for p in confirm_patterns)
                                # Always use the earlier per-message detection as the authoritative source
                                try:
                                    wrap_confirm = bool(locals().get("wrap_confirm_now", False))
                                    # Additional patterns for robustness at conversation level
                                    if not wrap_confirm:
                                        if (
                                            ("that's enough" in lm_l)
                                            or ("thats enough" in lm_l)
                                            or ("ready for advice" in lm_l)
                                            or ("i'm ready for advice" in lm_l)
                                            or ("i am ready for advice" in lm_l)
                                            or ("done with intake" in lm_l)
                                            or ("move to advice" in lm_l)
                                            or ("go ahead" in lm_l)
                                        ):
                                            wrap_confirm = True
                                except Exception:
                                    pass
                            except Exception:
                                wrap_confirm = False
                            # Heuristic fallback across recent context when not explicitly confirmed
                            goal_any = bool(locals().get("advice_intent", False))
                            partner_any = False
                            timeframe_any = False
                            try:
                                # Look at last up to 6 turns of history (user-focused) for signals
                                recent_hist = self._get_history_for_model(conversation_id, max_turns=6)
                                goal_pats = [
                                    r"\bmy goal is\b",
                                    r"\bi (?:want|hope|need) to\b",
                                    r"\bwe (?:want|hope|need) to\b",
                                    r"\bnext steps?\b",
                                ]
                                partner_pats = [
                                    r"\bhusband\b", r"\bwife\b", r"\bspouse\b", r"\bpartner\b",
                                    r"\bgirlfriend\b", r"\bboyfriend\b",
                                ]
                                timeframe_pats = [
                                    r"\bthis week\b", r"\bnext (?:few\s+)?weeks\b", r"\bby (?:friday|monday|\d{1,2}/\d{1,2})\b",
                                    r"\bwithin (?:a|one)?\s*(?:month|weeks?)\b", r"\bsoon\b",
                                ]
                                for m in (recent_hist or []):
                                    try:
                                        if (m or {}).get("role") != "user":
                                            continue
                                        txt = ((m or {}).get("content") or "").lower()
                                        if not goal_any and any(re.search(p, txt, re.I) for p in goal_pats):
                                            goal_any = True
                                        if not partner_any and any(re.search(p, txt, re.I) for p in partner_pats):
                                            partner_any = True
                                        if not timeframe_any and any(re.search(p, txt, re.I) for p in timeframe_pats):
                                            timeframe_any = True
                                    except Exception:
                                        continue
                            except Exception:
                                pass
                            # Determine assistant turns seen from DB-derived index (canonical)
                            try:
                                turns_seen = int(locals().get("assistant_turn_index", 0))
                            except Exception:
                                turns_seen = 0
                            # Apply heuristic completion when appropriate and not already complete/confirmed
                            try:
                                cls_conf_loc = float(locals().get("cls_conf", 0.0))
                            except Exception:
                                cls_conf_loc = 0.0
                            if not wrap_confirm and not intake_state.is_complete():
                                heuristic_ok = (
                                    (cls_conf_loc >= 0.6 and goal_any and (partner_any or timeframe_any))
                                    or (turns_seen >= 5 and bool(locals().get("advice_intent", False)) and cls_conf_loc >= 0.7)
                                )
                                if heuristic_ok:
                                    intake_state.issue_named = True
                                    intake_state.safety_cleared = True
                                    intake_state.goal_captured = True
                            if wrap_confirm:
                                intake_state.issue_named = True
                                intake_state.safety_cleared = True
                                intake_state.goal_captured = True
                                # When user explicitly confirms wrap-up, treat as implicit consent for faith guidance
                                intake_state.prayer_consent_known = True
                                # prayer_consent_known remains as captured; do not force without consent
                                try:
                                    logger.info("intake_confirm", extra={"cid": conversation_id, "path": "legacy"})
                                except Exception:
                                    pass
                            # Log intake state snapshot for observability
                            try:
                                logger.info(
                                    "intake_state",
                                    extra={
                                        "cid": conversation_id,
                                        "path": "legacy",
                                        "complete": bool(intake_state.is_complete()),
                                        "turns_seen": int(locals().get("assistant_turn_index", 0)),
                                        "goal": bool(goal_any),
                                        "partner": bool(partner_any),
                                        "timeframe": bool(timeframe_any),
                                        "topic_conf": cls_conf_loc,
                                    },
                                )
                            except Exception:
                                pass
                            # Merge back to meta
                            _intake_meta = intake_state.to_meta()
                            meta.setdefault("intake", {})
                            meta["intake"].update(_intake_meta.get("intake", {}))
                            meta["intake_completed"] = bool(intake_state.is_complete())
                            
                            # Debug log before any overrides
                            logger.warning(
                                "pre_override_intake_state",
                                extra={
                                    "cid": conversation_id,
                                    "path": "legacy", 
                                    "intake_state_complete": intake_state.is_complete(),
                                    "intake_state_flags": {
                                        "issue_named": intake_state.issue_named,
                                        "safety_cleared": intake_state.safety_cleared,
                                        "goal_captured": intake_state.goal_captured,
                                        "prayer_consent_known": intake_state.prayer_consent_known,
                                    },
                                    "meta_intake": meta.get("intake", {}),
                                    "meta_intake_completed": meta.get("intake_completed"),
                                },
                            )
                            
                            # Deterministic override: if the user explicitly affirmed wrap-up this turn,
                            # persist completion regardless of prayer_consent_known state.
                            if wrap_confirm:
                                try:
                                    meta["intake"]["completed"] = True
                                    meta["intake_completed"] = True
                                    # Force all intake flags in meta to True
                                    meta["intake"]["issue_named"] = True
                                    meta["intake"]["safety_cleared"] = True
                                    meta["intake"]["goal_captured"] = True
                                    meta["intake"]["prayer_consent_known"] = True
                                    
                                    logger.warning(
                                        "intake_override_complete",
                                        extra={
                                            "cid": conversation_id,
                                            "path": "legacy",
                                            "wrap_confirm": True,
                                            "meta_intake_after_override": meta.get("intake", {}),
                                            "meta_intake_completed_after_override": meta.get("intake_completed"),
                                        },
                                    )
                                except Exception:
                                    pass
                        except Exception:
                            # Fallback to previous flag if present
                            meta["intake_completed"] = bool(meta.get("intake_completed", False))
                        # Persist cadence snapshot for frontend badges
                        try:
                            meta["cadence_reason"] = cadence_reason
                            meta["allow_jesus_last"] = bool(locals().get("allow_jesus_invite", False))
                            meta["allow_books_last"] = bool(locals().get("allow_book_insertion", False))
                        except Exception:
                            pass
                        # Log meta diff summary
                        try:
                            interesting_keys = [
                                "declined_jesus_until_turn",
                                "jesus_decline_count",
                                "last_jesus_invite_turn",
                                "prayer_consent_known",
                                "prayer_consent",
                                "intake_completed",
                                "conversation_phase",
                                "allow_book_insertion_last",
                                "safety_flag_last",
                                "cadence_reason",
                                "allow_jesus_last",
                                "allow_books_last",
                            ]
                            changes = {}
                            for k in interesting_keys:
                                if old_meta.get(k) != meta.get(k):
                                    changes[k] = {"old": old_meta.get(k), "new": meta.get(k)}
                            logger.info("meta_diff", extra={"cid": conversation_id, "path": "legacy", "changes": changes})
                        except Exception:
                            pass
                        # Assign a fresh dict so SQLAlchemy detects JSON changes without MutableDict
                        conv.metadata_json = dict(meta)
                        try:
                            flag_modified(conv, "metadata_json")
                        except Exception:
                            pass
                        conv.updated_at = datetime.now(timezone.utc)
                        db.add(conv)
                        # Ensure changes are flushed before commit for reliability
                        try:
                            db.flush()
                        except Exception:
                            pass
                        db.commit()
                        # Verification step: in a fresh session, ensure intake completion persisted
                        try:
                            # Only verify when we detected completion/confirmation this turn
                            if bool(locals().get("wrap_confirm_now", False)) or bool(locals().get("intake_completed_now", False)) or bool(locals().get("wrap_confirm", False)):
                                vdb = SessionLocal()
                                try:
                                    vrow = (
                                        vdb.query(SQLConversation)
                                        .filter(SQLConversation.id == conversation_id)
                                        .first()
                                    )
                                    if vrow:
                                        vmeta = getattr(vrow, "metadata_json", None) or {}
                                        vintake = vmeta.get("intake") if isinstance(vmeta, dict) else {}
                                        completed_persisted = bool(isinstance(vintake, dict) and vintake.get("completed"))
                                        if not completed_persisted:
                                            vmeta.setdefault("intake", {})
                                            vmeta["intake"].update(
                                                {
                                                    "completed": True,
                                                    "issue_named": True,
                                                    "safety_cleared": True,
                                                    "goal_captured": True,
                                                    "prayer_consent_known": True,
                                                }
                                            )
                                            # Assign a fresh dict to trigger change detection
                                            vrow.metadata_json = dict(vmeta)
                                            try:
                                                flag_modified(vrow, "metadata_json")
                                            except Exception:
                                                pass
                                            vdb.add(vrow)
                                            vdb.commit()
                                finally:
                                    vdb.close()
                        except Exception:
                            # Non-fatal: API metadata will still reflect completion; DB verification failed
                            pass
                finally:
                    db.close()
                    try:
                        SessionLocal.remove()  # type: ignore[misc]
                    except Exception:
                        pass
                    try:
                        # Ensure scoped_session does not retain stale identity map across requests
                        SessionLocal.remove()  # type: ignore[name-defined]
                    except Exception:
                        pass
            except Exception as _e:
                logger.warning("Failed to update conversation metadata: %s", _e)

            # Align the returned assistant message metadata with the persisted intake completion
            # If wrap-up was confirmed this turn (by either early or later detection),
            # ensure the API response reflects intake completion and removes intake gating.
            try:
                # Prefer the canonical state we just computed/persisted on the conversation,
                # but also fall back to the local wrap confirmation signal for robustness.
                meta_intake = (meta.get("intake") if isinstance(meta, dict) else None) or {}
                completed_canonical = bool(meta_intake.get("completed"))
                # Fallback: rely on local detection flags if present
                try:
                    completed_canonical = bool(
                        completed_canonical
                        or bool(locals().get("wrap_confirm_now", False))
                        or bool(locals().get("wrap_confirm", False))
                    )
                except Exception:
                    pass

                if completed_canonical:
                    am_meta = getattr(assistant_msg, "metadata", None) or {}
                    # Ensure intake block exists and force flags true on the returned message
                    am_meta.setdefault("intake", {})
                    # Merge any persisted values first
                    if isinstance(meta_intake, dict):
                        am_meta["intake"].update(meta_intake)
                    # Deterministically set completion flags on the message metadata
                    am_meta["intake"].update(
                        {
                            "completed": True,
                            "issue_named": True,
                            "safety_cleared": True,
                            "goal_captured": True,
                            "prayer_consent_known": True,
                        }
                    )
                    # Clear intake gating on the message metadata if present
                    if am_meta.get("gate_reason") == "intake_incomplete":
                        am_meta["gate_reason"] = "ok"
                    assistant_msg.metadata = am_meta
            except Exception:
                pass

            return assistant_msg

        except urllib.error.HTTPError as he:
            body = None
            try:
                body = he.read().decode("utf-8", errors="ignore")
            except Exception:
                body = None
            logger.error(f"HTTPError generating response: {he} body={body}")
            # Return a helpful error message
            error_msg = await self.add_message(
                conversation_id=conversation_id,
                user_id="system",
                content="I'm sorry, I encountered an error while processing your message. Please try again.",
                role=MessageRole.SYSTEM,
                message_type=MessageType.TEXT,
                metadata={"error": str(he), "body": body},
            )
            return error_msg
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            # Return a helpful error message
            error_msg = await self.add_message(
                conversation_id=conversation_id,
                user_id="system",
                content="I'm sorry, I encountered an error while processing your message. Please try again.",
                role=MessageRole.SYSTEM,
                message_type=MessageType.TEXT,
                metadata={"error": str(e)},
            )
            return error_msg


def get_chat_service() -> ChatService:
    """Dependency for getting the chat service."""
    return ChatService()
