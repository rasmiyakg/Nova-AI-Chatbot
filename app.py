import os
import re
import uuid

import streamlit as st
from dotenv import load_dotenv
from groq import Groq


# =========================================================
# CONFIGURATION
# =========================================================

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

st.set_page_config(
    page_title="Nova AI",
    page_icon="N",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =========================================================
# CUSTOM CSS
# Theme-aware styling: avoids fixed dark backgrounds.
# =========================================================

st.markdown(
    """
    <style>
    .block-container {
        max-width: 1000px;
        padding-top: 2rem;
        padding-bottom: 7rem;
    }

    section[data-testid="stSidebar"] > div {
        padding-top: 1.5rem;
    }

    .nova-brand {
        font-size: 28px;
        font-weight: 800;
        letter-spacing: -1px;
        color: var(--text-color);
        margin-bottom: 4px;
    }

    .nova-brand span {
        color: var(--primary-color);
    }

    .nova-tagline {
        font-size: 13px;
        opacity: 0.7;
        color: var(--text-color);
        margin-bottom: 28px;
    }

    .sidebar-heading {
        font-size: 12px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1px;
        opacity: 0.65;
        margin-top: 26px;
        margin-bottom: 12px;
        color: var(--text-color);
    }

    .welcome-title {
        font-size: clamp(36px, 5vw, 56px);
        font-weight: 800;
        letter-spacing: -2px;
        line-height: 1.2;
        text-align: center;
        color: var(--text-color);
        margin-top: 14vh;
        margin-bottom: 20px;
    }

    .welcome-highlight {
        color: var(--primary-color);
    }

    .welcome-description {
        max-width: 580px;
        margin: 0 auto 35px auto;
        font-size: 16px;
        line-height: 1.8;
        text-align: center;
        color: var(--text-color);
        opacity: 0.72;
    }

    div[data-testid="stChatInput"] {
        max-width: 800px;
        margin-left: auto;
        margin-right: auto;
    }

    div[data-testid="stChatInput"] textarea {
        font-size: 15px;
    }

    div[data-testid="stChatMessage"] {
        padding-top: 0.7rem;
        padding-bottom: 0.7rem;
    }

    section[data-testid="stSidebar"] .stButton > button {
        text-align: left;
        justify-content: flex-start;
        min-height: 40px;
        font-size: 13px;
        border-radius: 9px;
    }

    .nova-footer {
        text-align: center;
        font-size: 12px;
        opacity: 0.55;
        color: var(--text-color);
        margin-top: 30px;
    }

    @media (max-width: 640px) {
        .block-container {
            padding-top: 1rem;
        }

        .welcome-title {
            margin-top: 8vh;
            letter-spacing: -1px;
        }

        .welcome-description {
            font-size: 14px;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# SESSION STATE
# =========================================================

if "messages" not in st.session_state:
    st.session_state.messages = []

if "conversations" not in st.session_state:
    st.session_state.conversations = []

if "active_conversation_id" not in st.session_state:
    st.session_state.active_conversation_id = uuid.uuid4().hex


# Repair duplicate or missing conversation IDs.

seen_ids = set()

for conversation in st.session_state.conversations:
    conversation_id = conversation.get("id")

    if not conversation_id or conversation_id in seen_ids:
        conversation_id = uuid.uuid4().hex
        conversation["id"] = conversation_id

    seen_ids.add(conversation_id)


# =========================================================
# EMOJI FILTER
# =========================================================

EMOJI_PATTERN = re.compile(
    "["
    "\U0001F000-\U0001FAFF"
    "\U0001FC00-\U0001FFFD"
    "\U00002600-\U000027BF"
    "\U0000FE00-\U0000FE0F"
    "\U0001F1E6-\U0001F1FF"
    "\U0001F3FB-\U0001F3FF"
    "\U0000200D"
    "\U000020E3"
    "\U00002300-\U000023FF"
    "\U00002B00-\U00002BFF"
    "]+",
    flags=re.UNICODE,
)


def remove_emojis(text):
    return EMOJI_PATTERN.sub("", text).strip()


# =========================================================
# CONVERSATION FUNCTIONS
# =========================================================

def get_conversation_title(messages):
    for message in messages:
        if message.get("role") == "user":
            question = message.get("content", "").strip()

            if len(question) > 35:
                return question[:35] + "..."

            return question or "New conversation"

    return "New conversation"


def save_active_conversation():
    messages = st.session_state.messages

    if not messages:
        return

    active_id = st.session_state.active_conversation_id

    saved = {
        "id": active_id,
        "title": get_conversation_title(messages),
        "messages": [message.copy() for message in messages],
    }

    existing_index = next(
        (
            index
            for index, conversation in enumerate(
                st.session_state.conversations
            )
            if conversation.get("id") == active_id
        ),
        None,
    )

    if existing_index is None:
        st.session_state.conversations.insert(0, saved)
    else:
        st.session_state.conversations[existing_index] = saved


def start_new_chat():
    save_active_conversation()
    st.session_state.messages = []
    st.session_state.active_conversation_id = uuid.uuid4().hex


# =========================================================
# GROQ API
# =========================================================

def get_ai_response(messages):
    if not GROQ_API_KEY:
        return (
            "The Groq API key is missing. Please check your .env file."
        )

    system_message = {
        "role": "system",
        "content": (
            "You are Nova AI, a helpful and intelligent AI assistant. "
            "Answer clearly and accurately. Explain technical topics "
            "in simple language when appropriate. Never use emojis or "
            "emoticons. Use readable paragraphs and lists when useful. "
            "If you are uncertain, say so honestly."
        ),
    }

    try:
        client = Groq(
            api_key=GROQ_API_KEY,
            timeout=60.0,
        )

        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[system_message] + messages,
            temperature=0.5,
            max_completion_tokens=1400,
        )

        answer = response.choices[0].message.content

        if not answer:
            return "I couldn't generate an answer. Please try again."

        return remove_emojis(answer)

    except Exception as error:
        print("Groq API error:", repr(error))

        return (
            "I couldn't generate a response. Please check your internet "
            "connection, API key, and model configuration."
        )


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    st.markdown(
        """
        <div class="nova-brand">Nova <span>AI</span></div>
        <div class="nova-tagline">
            Your space to think, learn, and create.
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button(
        "+ New Chat",
        key="nova_new_chat",
        use_container_width=True,
    ):
        start_new_chat()
        st.rerun()

    st.markdown(
        '<div class="sidebar-heading">Recent conversations</div>',
        unsafe_allow_html=True,
    )

    if not st.session_state.conversations:
        st.caption("Your conversations will appear here.")

    else:
        for index, conversation in enumerate(
            st.session_state.conversations
        ):
            conversation_id = conversation["id"]

            title = conversation.get(
                "title",
                get_conversation_title(
                    conversation.get("messages", [])
                ),
            )

            # Unique key for every button.
            button_key = (
                f"recent_chat_{index}_{conversation_id}"
            )

            if st.button(
                title,
                key=button_key,
                use_container_width=True,
            ):
                save_active_conversation()

                selected = next(
                    (
                        item
                        for item in st.session_state.conversations
                        if item.get("id") == conversation_id
                    ),
                    None,
                )

                if selected is not None:
                    st.session_state.messages = [
                        message.copy()
                        for message in selected.get("messages", [])
                    ]

                    st.session_state.active_conversation_id = (
                        conversation_id
                    )

                st.rerun()

    st.markdown("---")
    st.caption("Powered by Groq")


# =========================================================
# WELCOME SCREEN
# Use native Streamlit text to avoid raw HTML text.
# =========================================================

if not st.session_state.messages:

    st.markdown(
        '<div class="welcome-title">'
        'Ideas start here.<br>'
        '<span class="welcome-highlight">'
        "Let's make them real."
        "</span></div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="welcome-description">
            Ask questions, explore ideas, learn new skills,
            and solve problems in one simple workspace.
        </div>
        """,
        unsafe_allow_html=True,
    )


# =========================================================
# DISPLAY ASSISTANT ANSWERS
# No custom avatar path or invalid avatar="N".
# =========================================================

for message in st.session_state.messages:

    if message.get("role") == "assistant":

        # Use Streamlit's default assistant avatar.
        with st.chat_message("assistant"):
            st.markdown(remove_emojis(message["content"]))


# =========================================================
# CHAT INPUT
# Enter submits the question; no separate Send button.
# =========================================================

user_prompt = st.chat_input(
    "Message Nova AI...",
    key="nova_chat_input",
)

if user_prompt and user_prompt.strip():

    user_prompt = user_prompt.strip()

    st.session_state.messages.append(
        {
            "role": "user",
            "content": user_prompt,
        }
    )

    with st.spinner("Nova AI is thinking..."):
        answer = get_ai_response(st.session_state.messages)

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": remove_emojis(answer),
        }
    )

    save_active_conversation()
    st.rerun()


# =========================================================
# FOOTER
# =========================================================

st.markdown(
    '<div class="nova-footer">Nova AI</div>',
    unsafe_allow_html=True,
)

