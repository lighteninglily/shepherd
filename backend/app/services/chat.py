import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import json
import urllib.request
import urllib.error
import os
import inspect
import re
from pathlib import Path

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

        # Load API key. We log masked info to diagnose precedence issues.
        settings = get_settings()
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
            title = f"Conversation {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}"
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
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
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
                created_at=datetime.utcnow(),
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
                # Shallow merge; keys in provided metadata override existing
                current.update(metadata)
                obj.metadata_json = current
            obj.updated_at = datetime.utcnow()
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
                    "CONVERSATIONAL MODE: Keep replies concise (3–7 sentences). "
                    "Use brief reflective listening, then end with one open, non-leading question to invite the next turn. "
                    "Avoid long lists or multi-step plans in the first turn unless asked. "
                    "Include at most one Scripture (unless declined). "
                    "Offer one concrete 'do this today' action, then pause and ask permission to go deeper."
                )
            })
            # Normalize user content early for downstream heuristics
            lower_msg = (message or "").lower()

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

                    # Book insights: surface up to 5 named sources with 1 quick cue + 1 citation each
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

                        book_cues = []
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
                            bits = [pretty]
                            if citation:
                                bits.append(f"({citation})")
                            if cue:
                                bits.append(f": {cue}")
                            book_cues.append(" ".join(bits))
                        if book_cues:
                            summary_parts.append("Books: " + " | ".join(book_cues))
                            summary_parts.append(
                                "When offering counsel, explicitly attribute 1–2 insights to the named books (e.g., 'Keller's The Meaning of Marriage highlights…')."
                            )

                    # Enforce scripture + decisive action in answers
                    summary_parts.append(
                        "Always include exactly one Scripture (unless the user declines) and one specific 'do this today' action."
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

            # Extract the assistant's response
            assistant_message = data["choices"][0]["message"]["content"]

            # Create and save the assistant's response
            assistant_msg = await self.add_message(
                conversation_id=conversation_id,
                user_id="assistant",  # Or use a system user ID
                content=assistant_message,
                role=MessageRole.ASSISTANT,
                message_type=MessageType.TEXT,
                metadata={
                    "model": self.model,
                },
            )
            # Update conversation metadata/state
            try:
                from ..models.sql_models import Conversation as SQLConversation
                from ..db.base import SessionLocal
                db = SessionLocal()
                try:
                    conv = db.query(SQLConversation).filter(SQLConversation.id == conversation_id).first()
                    if conv:
                        meta = getattr(conv, "metadata_json", None) or {}
                        # Increment turns
                        meta["turns"] = int(meta.get("turns", 0)) + 1
                        # Detect consent for prayer from user message
                        lm = (message or "").lower()
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
                        # Detect last scripture used from assistant message
                        am = assistant_message
                        scripture_match = re.search(r"\b(?:[1-3]\s*)?[A-Za-z]+\s+\d+:\d+(?:-\d+)?\b", am)
                        if scripture_match:
                            meta["last_scripture_used"] = scripture_match.group(0)
                        # Heuristic trust rebuild stage
                        am_l = am.lower()
                        if any(k in am_l for k in ["transparency", "weekly actions", "accountability"]):
                            meta["trust_rebuild_stage"] = "early_repair"
                        # Intake completion heuristic: after first turn, consider completed
                        if meta.get("turns", 0) >= 1:
                            meta["intake_completed"] = True
                        conv.metadata_json = meta
                        conv.updated_at = datetime.utcnow()
                        db.add(conv)
                        db.commit()
                finally:
                    db.close()
            except Exception as _e:
                logger.warning("Failed to update conversation metadata: %s", _e)

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
