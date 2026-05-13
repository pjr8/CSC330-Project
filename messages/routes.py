from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from flask import (
    Blueprint,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    session,
)

from email_notifications import send_group_message_notification


messages_bp = Blueprint("messages", __name__)
EASTERN_TIME = ZoneInfo("America/New_York")


@messages_bp.get("/messages")
def inbox() -> str:
    store = _data_store()
    current_user = _current_user(store)
    current_user_id = _current_user_id(current_user)
    state = _message_page_state(
        store,
        current_user_id,
        search_query=request.args.get("q", ""),
        requested_chat_id=request.args.get("chat", ""),
        requested_group_id=request.args.get("group", ""),
    )

    return render_template(
        "messages.html",
        current_user=current_user,
        **state,
    )


@messages_bp.post("/messages/send")
def send_message():
    store = _data_store()
    current_user = _current_user(store)
    current_user_id = _current_user_id(current_user)

    content = request.form.get("content", request.form.get("message", "")).strip()
    conversation_id = request.form.get("conversation_id", "").strip()
    group_id = request.form.get("group_id", "").strip()
    search_query = request.form.get("q", "").strip()
    sent = False
    next_chat_id = conversation_id

    if content:
        result = _send_group_message(
            store,
            current_user_id,
            group_id=group_id or None,
            conversation_id=conversation_id or None,
            content=content,
        )
        next_chat_id = _field(result, "conversation_id", default=conversation_id)
        sent = result is not None
        if sent:
            _send_message_email_notification(store, current_user_id, result)
        if next_chat_id:
            if _wants_json_response():
                return _json_state_response(
                    store,
                    current_user_id,
                    search_query=search_query,
                    requested_chat_id=str(next_chat_id),
                    sent=sent,
                )
            return redirect(_messages_url(chat=str(next_chat_id), q=search_query))

    if _wants_json_response():
        return _json_state_response(
            store,
            current_user_id,
            search_query=search_query,
            requested_chat_id=next_chat_id,
            requested_group_id=group_id,
            sent=sent,
        )

    if conversation_id:
        return redirect(_messages_url(chat=conversation_id, q=search_query))
    if group_id:
        return redirect(_messages_url(group=group_id, q=search_query))
    return redirect("/messages")


@messages_bp.get("/messages/state")
def message_state():
    store = _data_store()
    current_user = _current_user(store)
    current_user_id = _current_user_id(current_user)
    return _json_state_response(
        store,
        current_user_id,
        search_query=request.args.get("q", ""),
        requested_chat_id=request.args.get("chat", ""),
        requested_group_id=request.args.get("group", ""),
    )


@messages_bp.get("/messages/updates")
def message_updates():
    store = _data_store()
    current_user = _current_user(store)
    current_user_id = _current_user_id(current_user)
    conversation_id = request.args.get("chat", "").strip()

    if not conversation_id:
        response = jsonify({"ok": False, "messages": []})
        response.status_code = 400
        return response

    thread = _get_group_thread_messages(store, current_user_id, conversation_id)
    if thread is None:
        response = jsonify({"ok": False, "messages": []})
        response.status_code = 404
        return response

    response = jsonify(
        {
            "ok": True,
            "active_thread": _group_thread_view(
                _field(thread, "conversation", default={})
            ),
            "messages": [
                _message_view(message)
                for message in _field(thread, "messages", default=[])
            ],
        }
    )
    response.headers["Cache-Control"] = "no-store"
    return response


def _message_page_state(
    store: Any,
    current_user_id: str,
    *,
    search_query: str = "",
    requested_chat_id: str = "",
    requested_group_id: str = "",
) -> dict[str, Any]:
    search_query = search_query.strip()
    requested_chat_id = requested_chat_id.strip()
    requested_group_id = requested_group_id.strip()

    all_threads = [
        _group_thread_view(thread)
        for thread in _list_group_chats(store, current_user_id)
    ]
    threads = _filter_threads(all_threads, search_query)

    active_chat_id = requested_chat_id
    if requested_group_id and not active_chat_id:
        requested_group_thread = _group_chat_for_group(
            store,
            current_user_id,
            requested_group_id,
        )
        if requested_group_thread is not None:
            requested_group_view = _group_thread_view(requested_group_thread)
            active_chat_id = requested_group_view["conversation_id"]
            if not any(
                thread["conversation_id"] == requested_group_view["conversation_id"]
                for thread in threads
            ):
                threads = [requested_group_view, *threads]

    if not active_chat_id and threads:
        active_chat_id = threads[0]["conversation_id"]

    active_thread: dict[str, Any] | None = None
    thread_messages: list[dict[str, Any]] = []
    if active_chat_id:
        thread = _get_group_thread_messages(store, current_user_id, active_chat_id)
        if thread is not None:
            active_thread = _group_thread_view(_field(thread, "conversation", default={}))
            if not active_thread["conversation_id"]:
                active_thread["conversation_id"] = active_chat_id
            thread_messages = [
                _message_view(message)
                for message in _field(thread, "messages", default=[])
            ]
        else:
            active_chat_id = ""

    return {
        "threads": threads,
        "active_chat_id": active_chat_id,
        "active_thread": active_thread,
        "messages": thread_messages,
        "search_query": search_query,
    }


def _json_state_response(
    store: Any,
    current_user_id: str,
    *,
    search_query: str = "",
    requested_chat_id: str = "",
    requested_group_id: str = "",
    sent: bool | None = None,
):
    payload: dict[str, Any] = {
        "ok": True,
        "state": _message_page_state(
            store,
            current_user_id,
            search_query=search_query,
            requested_chat_id=requested_chat_id,
            requested_group_id=requested_group_id,
        ),
    }
    if sent is not None:
        payload["sent"] = sent

    response = jsonify(payload)
    response.headers["Cache-Control"] = "no-store"
    return response


def _wants_json_response() -> bool:
    return (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or "application/json" in request.headers.get("Accept", "")
    )


def _data_store() -> Any:
    return current_app.config["DATA_STORE"]


def _current_user(store: Any) -> Any:
    return store.user_for_session(session.get("user_id"))


def _current_user_id(current_user: Any) -> str:
    user_id = _field(current_user, "id", default=session.get("user_id", ""))
    return str(user_id)


def _list_group_chats(store: Any, current_user_id: str) -> list[Any]:
    return store.list_user_study_group_chats(current_user_id)


def _group_chat_for_group(
    store: Any,
    current_user_id: str,
    group_id: str,
) -> Any | None:
    get_chat = getattr(store, "get_study_group_chat_for_group", None)
    if get_chat is None:
        return None

    return get_chat(current_user_id, group_id)


def _get_group_thread_messages(
    store: Any,
    current_user_id: str,
    conversation_id: str,
) -> Any | None:
    return store.get_study_group_thread_messages(current_user_id, conversation_id)


def _send_group_message(
    store: Any,
    current_user_id: str,
    *,
    group_id: str | None,
    conversation_id: str | None,
    content: str,
) -> Any | None:
    return store.send_study_group_message(
        current_user_id,
        group_id=group_id,
        conversation_id=conversation_id,
        content=content,
    )


def _send_message_email_notification(
    store: Any,
    current_user_id: str,
    result: Any,
) -> None:
    group_id = _field(result, "group_id", default="")
    message = _field(result, "message", default=None)
    content = _field(message, "content", default="")
    if not group_id or not content:
        return

    notification_data_loader = getattr(store, "group_message_notification_data", None)
    if notification_data_loader is None:
        return

    notification_data = notification_data_loader(group_id, current_user_id)
    if notification_data is None:
        return

    send_group_message_notification(
        recipients=list(_field(notification_data, "recipients", default=[])),
        group_title=str(_field(notification_data, "group_title", default="Study group")),
        sender_name=str(
            _field(notification_data, "sender_name", default="A group member")
        ),
        content=str(content),
    )


def _filter_threads(
    threads: list[dict[str, Any]],
    search_query: str,
) -> list[dict[str, Any]]:
    terms = search_query.casefold().split()
    if not terms:
        return threads

    return [
        thread
        for thread in threads
        if all(term in _thread_search_text(thread) for term in terms)
    ]


def _thread_search_text(thread: dict[str, Any]) -> str:
    return " ".join(
        str(thread.get(field_name, ""))
        for field_name in (
            "group_title",
            "group_subject",
            "group_location",
            "group_modality",
            "last_message",
        )
    ).casefold()


def _group_thread_view(thread: Any) -> dict[str, Any]:
    group_title = _field(
        thread,
        "group_title",
        "title",
        "participant_name",
        "display_name",
        "name",
        default="Study group",
    )
    group_subject = _field(
        thread,
        "group_subject",
        "subject",
        "participant_major",
        default="",
    )
    member_count = _field(thread, "member_count", "members_count", default=0)
    last_sent_at = _field(thread, "last_sent_at", "last_message_at", default="")

    return {
        "conversation_id": str(
            _field(thread, "conversation_id", "chat_id", "id", default="")
        ),
        "group_id": str(_field(thread, "group_id", default="")),
        "group_title": group_title,
        "group_subject": group_subject,
        "group_modality": _field(thread, "group_modality", "modality", default=""),
        "group_location": _field(thread, "group_location", "location", default=""),
        "group_status": _field(thread, "group_status", "status", default=""),
        "member_count": int(member_count or 0),
        "last_message": _field(thread, "last_message", "preview", default=""),
        "last_sent_at": last_sent_at,
        "last_sent_at_label": _format_eastern_timestamp(last_sent_at),
        "initials": _initials(str(group_title)),
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

    sent_at = _field(message, "sent_at", "sentAt", default="")
    return {
        "id": str(_field(message, "id", default="")),
        "sender_name": sender_name,
        "content": _field(message, "content", "text", "message", default=""),
        "sent_at": sent_at,
        "sent_at_label": _format_eastern_timestamp(sent_at),
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
        return "SG"
    return "".join(part[0].upper() for part in parts[:2])


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes", "mine"}
    return bool(value)


def _format_eastern_timestamp(value: Any) -> str:
    if not value:
        return ""

    if isinstance(value, datetime):
        timestamp = value
    else:
        try:
            timestamp = datetime.fromisoformat(str(value))
        except ValueError:
            return str(value)

    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=EASTERN_TIME)
    else:
        timestamp = timestamp.astimezone(EASTERN_TIME)

    hour = timestamp.hour % 12 or 12
    meridiem = "AM" if timestamp.hour < 12 else "PM"
    return (
        f"{timestamp.strftime('%B')} {timestamp.day}, {timestamp.year} "
        f"at {hour}:{timestamp.minute:02d} {meridiem} ET"
    )


def _messages_url(**params: str) -> str:
    clean_params = {
        key: value
        for key, value in params.items()
        if value
    }
    if not clean_params:
        return "/messages"
    return f"/messages?{urlencode(clean_params)}"
