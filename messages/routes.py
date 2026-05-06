from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from flask import Blueprint, current_app, redirect, render_template, request, session


messages_bp = Blueprint("messages", __name__)


@messages_bp.get("/messages")
def inbox() -> str:
    store = _data_store()
    current_user = _current_user(store)
    current_user_id = _current_user_id(current_user)

    search_query = request.args.get("q", "").strip()
    requested_chat_id = request.args.get("chat", "").strip()
    requested_recipient_id = request.args.get("recipient", "").strip()

    threads = [
        _thread_view(thread)
        for thread in store.list_user_dm_threads(current_user_id)
    ]
    search_results = _search_results(store, current_user_id, search_query)
    selected_recipient = _selected_recipient(
        requested_recipient_id,
        search_results,
    )

    active_chat_id = requested_chat_id
    if not active_chat_id and selected_recipient is None and not search_query and threads:
        active_chat_id = threads[0]["conversation_id"]

    active_thread: dict[str, Any] | None = None
    thread_messages: list[dict[str, Any]] = []
    if active_chat_id:
        thread = store.get_dm_thread_messages(current_user_id, active_chat_id)
        if thread is not None:
            active_thread = _thread_view(_field(thread, "conversation", default={}))
            if not active_thread["conversation_id"]:
                active_thread["conversation_id"] = active_chat_id
            thread_messages = [
                _message_view(message)
                for message in _field(thread, "messages", default=[])
            ]
        else:
            active_chat_id = ""

    return render_template(
        "messages.html",
        current_user=current_user,
        threads=threads,
        active_chat_id=active_chat_id,
        active_thread=active_thread,
        messages=thread_messages,
        search_query=search_query,
        search_results=search_results,
        selected_recipient=selected_recipient,
    )


@messages_bp.post("/messages/send")
def send_message():
    store = _data_store()
    current_user = _current_user(store)
    current_user_id = _current_user_id(current_user)

    content = request.form.get("content", request.form.get("message", "")).strip()
    conversation_id = request.form.get("conversation_id", "").strip()
    recipient_id = request.form.get("recipient_id", "").strip()
    search_query = request.form.get("q", "").strip()

    if content:
        result = store.send_direct_message(
            current_user_id,
            recipient_id=recipient_id or None,
            conversation_id=conversation_id or None,
            content=content,
        )
        next_chat_id = _field(result, "conversation_id", default=conversation_id)
        if next_chat_id:
            return redirect(_messages_url(chat=str(next_chat_id)))

    if conversation_id:
        return redirect(_messages_url(chat=conversation_id))
    if recipient_id:
        return redirect(_messages_url(recipient=recipient_id, q=search_query))
    return redirect("/messages")


def _data_store() -> Any:
    return current_app.config["DATA_STORE"]


def _current_user(store: Any) -> Any:
    return store.user_for_session(session.get("user_id"))


def _current_user_id(current_user: Any) -> str:
    user_id = _field(current_user, "id", default=session.get("user_id", ""))
    return str(user_id)


def _search_results(
    store: Any,
    current_user_id: str,
    search_query: str,
) -> list[dict[str, Any]]:
    if not search_query:
        return []

    return [
        _user_result_view(user)
        for user in store.search_users_for_dm(current_user_id, search_query)
    ]


def _selected_recipient(
    recipient_id: str,
    search_results: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not recipient_id:
        return None

    for user in search_results:
        if str(user["id"]) == recipient_id:
            return user

    return {
        "id": recipient_id,
        "name": "Selected student",
        "email": "",
        "major": "",
    }


def _thread_view(thread: Any) -> dict[str, Any]:
    first_name = _field(thread, "first_name", "firstName", default="")
    last_name = _field(thread, "last_name", "lastName", default="")
    email = _field(thread, "scsu_email", "email", "scsuEmail", default="")
    participant_name = _field(
        thread,
        "participant_name",
        "display_name",
        "full_name",
        "name",
        default="",
    )
    if not participant_name:
        participant_name = _display_name(first_name, last_name, email, "Conversation")

    return {
        "conversation_id": str(
            _field(thread, "conversation_id", "chat_id", "id", default="")
        ),
        "participant_id": str(
            _field(thread, "participant_id", "recipient_id", "user_id", default="")
        ),
        "participant_name": participant_name,
        "participant_email": email,
        "participant_major": _field(thread, "major", "participant_major", default=""),
        "last_message": _field(thread, "last_message", "preview", default=""),
        "last_sent_at": _field(thread, "last_sent_at", "last_message_at", default=""),
        "initials": _initials(participant_name),
    }


def _user_result_view(user: Any) -> dict[str, Any]:
    first_name = _field(user, "first_name", "firstName", default="")
    last_name = _field(user, "last_name", "lastName", default="")
    email = _field(user, "scsu_email", "email", "scsuEmail", default="")
    name = _field(user, "display_name", "full_name", "name", default="")
    if not name:
        name = _display_name(first_name, last_name, email, "Student")

    return {
        "id": str(_field(user, "id", "user_id", default="")),
        "name": name,
        "email": email,
        "major": _field(user, "major", default=""),
        "initials": _initials(name),
    }


def _message_view(message: Any) -> dict[str, Any]:
    first_name = _field(message, "first_name", "firstName", default="")
    last_name = _field(message, "last_name", "lastName", default="")
    email = _field(message, "scsu_email", "email", "scsuEmail", default="")
    sender_name = _field(
        message,
        "sender_name",
        "display_name",
        "sender",
        "name",
        default="",
    )
    if not sender_name:
        sender_name = _display_name(first_name, last_name, email, "Student")

    return {
        "id": str(_field(message, "id", default="")),
        "sender_name": sender_name,
        "content": _field(message, "content", "text", "message", default=""),
        "sent_at": _field(message, "sent_at", "sentAt", default=""),
        "is_mine": _as_bool(_field(message, "is_mine", default=False)),
    }


def _field(value: Any, *names: str, default: Any = None) -> Any:
    if value is None:
        return default

    if isinstance(value, dict):
        for name in names:
            if name in value:
                return value[name]
        return default

    for name in names:
        if hasattr(value, name):
            return getattr(value, name)
    return default


def _display_name(
    first_name: Any,
    last_name: Any,
    email: Any,
    fallback: str,
) -> str:
    name = f"{first_name or ''} {last_name or ''}".strip()
    if name:
        return name
    if email:
        return str(email)
    return fallback


def _initials(name: str) -> str:
    parts = [part for part in name.replace("@", " ").split() if part]
    if not parts:
        return "SC"
    return "".join(part[0].upper() for part in parts[:2])


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes", "mine"}
    return bool(value)


def _messages_url(**params: str) -> str:
    clean_params = {
        key: value
        for key, value in params.items()
        if value
    }
    if not clean_params:
        return "/messages"
    return f"/messages?{urlencode(clean_params)}"
