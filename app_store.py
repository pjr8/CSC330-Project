from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from werkzeug.security import check_password_hash, generate_password_hash

from accounts.store import normalize_email
from models import (
    GroupMembership,
    Message,
    NotificationPreference,
    StudyGroup,
    User,
)


DEFAULT_USER_EMAIL = "test@southernct.edu"
APP_NAMESPACE = uuid5(NAMESPACE_URL, "https://github.com/pjr8/CSC330-Project")


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    scsu_email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL DEFAULT '',
    first_name TEXT NOT NULL DEFAULT '',
    last_name TEXT NOT NULL DEFAULT '',
    major TEXT NOT NULL DEFAULT '',
    interests TEXT NOT NULL DEFAULT '[]',
    bio TEXT NOT NULL DEFAULT '',
    profile_image_url TEXT NOT NULL DEFAULT '',
    contact_info TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active',
    role TEXT NOT NULL DEFAULT 'student',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notification_preferences (
    user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    email_enabled INTEGER NOT NULL DEFAULT 1,
    in_app_enabled INTEGER NOT NULL DEFAULT 1,
    message_alerts INTEGER NOT NULL DEFAULT 1,
    reminder_alerts INTEGER NOT NULL DEFAULT 1,
    group_update_alerts INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS study_groups (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    subject TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    start_at TEXT,
    end_at TEXT,
    modality TEXT NOT NULL DEFAULT '',
    location TEXT NOT NULL DEFAULT '',
    meeting_link TEXT NOT NULL DEFAULT '',
    max_members INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL,
    creator_id TEXT REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS group_memberships (
    id TEXT PRIMARY KEY,
    member_id TEXT REFERENCES users(id) ON DELETE CASCADE,
    group_id TEXT REFERENCES study_groups(id) ON DELETE CASCADE,
    joined_at TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'member',
    status TEXT NOT NULL DEFAULT 'active',
    UNIQUE(member_id, group_id)
);

CREATE TABLE IF NOT EXISTS favorite_study_groups (
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    group_id TEXT NOT NULL REFERENCES study_groups(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, group_id)
);

CREATE TABLE IF NOT EXISTS reviews (
    id TEXT PRIMARY KEY,
    reviewer_id TEXT REFERENCES users(id) ON DELETE SET NULL,
    group_id TEXT REFERENCES study_groups(id) ON DELETE CASCADE,
    rating INTEGER NOT NULL DEFAULT 0,
    comment TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS reports (
    id TEXT PRIMARY KEY,
    reporter_id TEXT REFERENCES users(id) ON DELETE SET NULL,
    target_type TEXT NOT NULL DEFAULT '',
    target_id TEXT,
    reason TEXT NOT NULL DEFAULT '',
    details TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL,
    resolved_at TEXT
);

CREATE TABLE IF NOT EXISTS notifications (
    id TEXT PRIMARY KEY,
    recipient_id TEXT REFERENCES users(id) ON DELETE CASCADE,
    message TEXT NOT NULL DEFAULT '',
    type TEXT NOT NULL DEFAULT '',
    related_target_type TEXT,
    related_target_id TEXT,
    created_at TEXT NOT NULL,
    read_at TEXT
);

CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL DEFAULT 'dm',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_message_at TEXT,
    status TEXT NOT NULL DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS conversation_participants (
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    joined_at TEXT NOT NULL,
    last_read_at TEXT,
    PRIMARY KEY (conversation_id, user_id)
);

CREATE TABLE IF NOT EXISTS direct_message_threads (
    conversation_id TEXT PRIMARY KEY REFERENCES conversations(id) ON DELETE CASCADE,
    user_one_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    user_two_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_one_id, user_two_id),
    CHECK(user_one_id <> user_two_id)
);

CREATE TABLE IF NOT EXISTS study_group_message_threads (
    conversation_id TEXT PRIMARY KEY REFERENCES conversations(id) ON DELETE CASCADE,
    group_id TEXT NOT NULL UNIQUE REFERENCES study_groups(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    sender_id TEXT REFERENCES users(id) ON DELETE SET NULL,
    content TEXT NOT NULL,
    sent_at TEXT NOT NULL,
    edited_at TEXT,
    status TEXT NOT NULL DEFAULT 'sent'
);

CREATE INDEX IF NOT EXISTS idx_conversation_participants_user
    ON conversation_participants(user_id);

CREATE INDEX IF NOT EXISTS idx_messages_conversation_sent
    ON messages(conversation_id, sent_at);

CREATE INDEX IF NOT EXISTS idx_study_group_message_threads_group
    ON study_group_message_threads(group_id);

CREATE INDEX IF NOT EXISTS idx_users_search
    ON users(first_name, last_name, scsu_email);
"""


class SQLiteStudyGroupStore:
    """SQLite persistence for the model dataclasses used by the Flask routes."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = str(database_path)

    def initialize(self) -> None:
        self._ensure_parent_directory()
        with self._connect() as conn:
            self._drop_legacy_message_tables(conn)
            conn.executescript(SCHEMA)
            self._seed_defaults(conn)
            self._ensure_study_group_threads(conn)

    def find_by_email(self, email: str) -> User | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE scsu_email = ?",
                (normalize_email(email),),
            ).fetchone()
            if row is None:
                return None

            user = self._user_from_row(row)
            self._apply_preference(conn, user)
            return user

    def create_user(self, user: User) -> User:
        user.scsuEmail = normalize_email(user.scsuEmail)
        with self._connect() as conn:
            try:
                self._insert_user(conn, user, ignore_existing=False)
            except sqlite3.IntegrityError as exc:
                raise ValueError("duplicate_email") from exc
        return user

    def authenticate_user(self, email: str, password: str) -> User | None:
        user = self.find_by_email(email)
        if user is None:
            return None

        if not user.passwordHash:
            return None

        if check_password_hash(user.passwordHash, password):
            return user

        return None

    def get_user(self, user_id: str | UUID | None) -> User | None:
        if not user_id:
            return None

        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE id = ?",
                (str(user_id),),
            ).fetchone()
            if row is None:
                return None

            user = self._user_from_row(row)
            self._apply_preference(conn, user)
            return user

    def user_for_session(self, user_id: str | UUID | None) -> User:
        user = self.get_user(user_id)
        if user is not None:
            return user

        default_user = self.find_by_email(DEFAULT_USER_EMAIL)
        if default_user is None:
            raise RuntimeError("Default user seed is missing from the SQLite database")

        return default_user

    def update_user_profile(
        self,
        user_id: str | UUID,
        *,
        first_name: str,
        last_name: str,
        major: str,
        bio: str,
        interests: list[str],
        contact_info: str,
    ) -> User:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE users
                SET first_name = ?,
                    last_name = ?,
                    major = ?,
                    bio = ?,
                    interests = ?,
                    contact_info = ?
                WHERE id = ?
                """,
                (
                    first_name,
                    last_name,
                    major,
                    bio,
                    json.dumps(interests),
                    contact_info,
                    str(user_id),
                ),
            )

        updated_user = self.get_user(user_id)
        if updated_user is None:
            raise RuntimeError("Updated user could not be reloaded from SQLite")

        return updated_user

    def study_group_listing_data(
        self, user_id: str | UUID | None
    ) -> tuple[User, list[StudyGroup]]:
        with self._connect() as conn:
            users = self._load_users(conn)
            groups = self._load_study_groups(conn, users)
            self._load_memberships(conn, users, groups)
            self._load_favorites(conn, users, groups)

            resolved_user_id = self._resolve_user_id(conn, user_id)
            current_user = users.get(resolved_user_id)
            if current_user is None:
                raise RuntimeError("Current user could not be loaded from SQLite")

            return current_user, list(groups.values())

    def study_group_detail_data(
        self,
        user_id: str | UUID | None,
        group_id: str | UUID,
    ) -> tuple[User, StudyGroup | None]:
        with self._connect() as conn:
            users = self._load_users(conn)
            groups = self._load_study_groups(conn, users)
            self._load_memberships(conn, users, groups)
            self._load_favorites(conn, users, groups)

            resolved_user_id = self._resolve_user_id(conn, user_id)
            current_user = users.get(resolved_user_id)
            if current_user is None:
                raise RuntimeError("Current user could not be loaded from SQLite")

            return current_user, groups.get(str(group_id))

    def create_study_group(
        self,
        user_id: str | UUID | None,
        *,
        title: str,
        subject: str,
        description: str,
        start_at: datetime | None,
        end_at: datetime | None,
        modality: str,
        location: str,
        meeting_link: str,
        max_members: int,
    ) -> StudyGroup:
        with self._connect() as conn:
            creator_id = self._resolve_user_id(conn, user_id)
            creator_row = conn.execute(
                "SELECT * FROM users WHERE id = ?",
                (creator_id,),
            ).fetchone()
            if creator_row is None:
                raise RuntimeError("Study group creator could not be loaded from SQLite")

            creator = self._user_from_row(creator_row)
            group = StudyGroup(
                title=title,
                subject=subject,
                description=description,
                startAt=start_at,
                endAt=end_at,
                modality=modality,
                location=location,
                meetingLink=meeting_link,
                maxMembers=max_members,
                creator=creator,
            )
            self._insert_study_group(conn, group, ignore_existing=False)
            self._insert_membership(
                conn,
                GroupMembership(member=creator, group=group, role="host"),
                ignore_existing=False,
            )
            self._ensure_study_group_thread(conn, str(group.id))

        return group

    def join_study_group(
        self,
        user_id: str | UUID | None,
        group_id: str | UUID,
    ) -> bool:
        with self._connect() as conn:
            member_id = self._resolve_user_id(conn, user_id)
            group_row = conn.execute(
                "SELECT * FROM study_groups WHERE id = ?",
                (str(group_id),),
            ).fetchone()
            if group_row is None or group_row["status"] != "open":
                return False

            existing_membership = conn.execute(
                """
                SELECT *
                FROM group_memberships
                WHERE member_id = ? AND group_id = ?
                """,
                (member_id, str(group_id)),
            ).fetchone()
            if (
                existing_membership is not None
                and existing_membership["status"] == "active"
            ):
                conversation_id = self._ensure_study_group_thread(conn, str(group_id))
                self._insert_conversation_participant(
                    conn,
                    conversation_id,
                    member_id,
                    ignore_existing=True,
                )
                return True

            active_member_count = conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM group_memberships
                WHERE group_id = ? AND status = 'active'
                """,
                (str(group_id),),
            ).fetchone()["count"]

            max_members = group_row["max_members"]
            if max_members > 0 and active_member_count >= max_members:
                return False

            joined_at = _format_datetime(datetime.now())
            if existing_membership is not None:
                conn.execute(
                    """
                    UPDATE group_memberships
                    SET joined_at = ?,
                        role = CASE WHEN role = 'host' THEN role ELSE 'member' END,
                        status = 'active'
                    WHERE id = ?
                    """,
                    (joined_at, existing_membership["id"]),
                )
                conversation_id = self._ensure_study_group_thread(conn, str(group_id))
                self._insert_conversation_participant(
                    conn,
                    conversation_id,
                    member_id,
                    ignore_existing=True,
                )
                return True

            conn.execute(
                """
                INSERT INTO group_memberships (
                    id,
                    member_id,
                    group_id,
                    joined_at,
                    role,
                    status
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    member_id,
                    str(group_id),
                    joined_at,
                    "member",
                    "active",
                ),
            )
            conversation_id = self._ensure_study_group_thread(conn, str(group_id))
            self._insert_conversation_participant(
                conn,
                conversation_id,
                member_id,
                ignore_existing=True,
            )
            return True

    def leave_study_group(
        self,
        user_id: str | UUID | None,
        group_id: str | UUID,
    ) -> bool:
        with self._connect() as conn:
            member_id = self._resolve_user_id(conn, user_id)
            membership = conn.execute(
                """
                SELECT group_memberships.*, study_groups.creator_id
                FROM group_memberships
                JOIN study_groups ON study_groups.id = group_memberships.group_id
                WHERE member_id = ? AND group_id = ?
                """,
                (member_id, str(group_id)),
            ).fetchone()
            if (
                membership is None
                or membership["status"] != "active"
                or membership["creator_id"] == member_id
                or membership["role"] == "host"
            ):
                return False

            conn.execute(
                """
                UPDATE group_memberships
                SET status = 'left'
                WHERE id = ?
                """,
                (membership["id"],),
            )
            conversation_id = self._study_group_thread_id_for_group(
                conn,
                str(group_id),
            )
            if conversation_id is not None:
                conn.execute(
                    """
                    DELETE FROM conversation_participants
                    WHERE conversation_id = ? AND user_id = ?
                    """,
                    (conversation_id, member_id),
                )
            return True

    def delete_study_group(
        self,
        user_id: str | UUID | None,
        group_id: str | UUID,
    ) -> bool:
        with self._connect() as conn:
            creator_id = self._resolve_user_id(conn, user_id)
            conversation_id = self._study_group_thread_id_for_group(
                conn,
                str(group_id),
            )
            cursor = conn.execute(
                """
                DELETE FROM study_groups
                WHERE id = ? AND creator_id = ?
                """,
                (str(group_id), creator_id),
            )
            deleted = cursor.rowcount > 0
            if deleted and conversation_id is not None:
                conn.execute(
                    "DELETE FROM conversations WHERE id = ?",
                    (conversation_id,),
                )
            return deleted

    def search_users_for_dm(
        self,
        current_user_id: str | UUID | None,
        query: str,
    ) -> list[dict[str, str]]:
        query = query.strip()
        if not query:
            return []

        with self._connect() as conn:
            resolved_user_id = self._resolve_user_id(conn, current_user_id)
            like_query = f"%{query.lower()}%"
            rows = conn.execute(
                """
                SELECT id, scsu_email, first_name, last_name, major
                FROM users
                WHERE id != ?
                    AND status = 'active'
                    AND (
                        lower(first_name || ' ' || last_name) LIKE ?
                        OR lower(scsu_email) LIKE ?
                        OR lower(major) LIKE ?
                    )
                ORDER BY first_name, last_name, scsu_email
                LIMIT 10
                """,
                (resolved_user_id, like_query, like_query, like_query),
            ).fetchall()

        return [self._user_search_result_from_row(row) for row in rows]

    def list_user_dm_threads(
        self,
        current_user_id: str | UUID | None,
    ) -> list[dict[str, str]]:
        with self._connect() as conn:
            resolved_user_id = self._resolve_user_id(conn, current_user_id)
            rows = conn.execute(
                """
                SELECT
                    c.id AS conversation_id,
                    c.last_message_at,
                    other.id AS participant_id,
                    other.scsu_email,
                    other.first_name,
                    other.last_name,
                    other.major,
                    latest.content AS last_message,
                    latest.sent_at AS last_sent_at
                FROM conversations c
                JOIN conversation_participants mine
                    ON mine.conversation_id = c.id
                    AND mine.user_id = ?
                JOIN direct_message_threads d
                    ON d.conversation_id = c.id
                JOIN users other
                    ON other.id = CASE
                        WHEN d.user_one_id = ? THEN d.user_two_id
                        ELSE d.user_one_id
                    END
                JOIN messages latest
                    ON latest.id = (
                        SELECT m.id
                        FROM messages m
                        WHERE m.conversation_id = c.id
                            AND m.status != 'deleted'
                        ORDER BY m.sent_at DESC
                        LIMIT 1
                    )
                WHERE c.status = 'active'
                ORDER BY COALESCE(c.last_message_at, latest.sent_at) DESC,
                    other.first_name,
                    other.last_name
                """,
                (resolved_user_id, resolved_user_id),
            ).fetchall()

        return [self._thread_summary_from_row(row) for row in rows]

    def get_dm_thread_messages(
        self,
        current_user_id: str | UUID | None,
        conversation_id: str | UUID,
    ) -> dict[str, object] | None:
        with self._connect() as conn:
            resolved_user_id = self._resolve_user_id(conn, current_user_id)
            thread_row = self._dm_thread_row(conn, resolved_user_id, str(conversation_id))
            if thread_row is None:
                return None

            message_rows = conn.execute(
                """
                SELECT m.*, u.first_name, u.last_name, u.scsu_email
                FROM messages m
                LEFT JOIN users u ON u.id = m.sender_id
                WHERE m.conversation_id = ?
                    AND m.status != 'deleted'
                ORDER BY m.sent_at ASC
                """,
                (str(conversation_id),),
            ).fetchall()

        return {
            "conversation": self._thread_summary_from_row(thread_row),
            "messages": [
                self._message_view_from_row(row, resolved_user_id)
                for row in message_rows
            ],
        }

    def list_user_study_group_chats(
        self,
        current_user_id: str | UUID | None,
    ) -> list[dict[str, object]]:
        with self._connect() as conn:
            resolved_user_id = self._resolve_user_id(conn, current_user_id)
            self._ensure_study_group_threads(conn)
            rows = conn.execute(
                """
                SELECT
                    c.id AS conversation_id,
                    c.last_message_at,
                    g.id AS group_id,
                    g.title AS group_title,
                    g.subject AS group_subject,
                    g.modality AS group_modality,
                    g.location AS group_location,
                    g.meeting_link AS group_meeting_link,
                    g.status AS group_status,
                    latest.content AS last_message,
                    latest.sent_at AS last_sent_at,
                    (
                        SELECT COUNT(*)
                        FROM group_memberships active_members
                        WHERE active_members.group_id = g.id
                            AND active_members.status = 'active'
                    ) AS member_count
                FROM group_memberships mine
                JOIN study_groups g
                    ON g.id = mine.group_id
                JOIN study_group_message_threads group_thread
                    ON group_thread.group_id = g.id
                JOIN conversations c
                    ON c.id = group_thread.conversation_id
                LEFT JOIN messages latest
                    ON latest.id = (
                        SELECT m.id
                        FROM messages m
                        WHERE m.conversation_id = c.id
                            AND m.status != 'deleted'
                        ORDER BY m.sent_at DESC
                        LIMIT 1
                    )
                WHERE mine.member_id = ?
                    AND mine.status = 'active'
                    AND c.status = 'active'
                ORDER BY COALESCE(c.last_message_at, g.start_at, g.created_at) DESC,
                    lower(g.title)
                """,
                (resolved_user_id,),
            ).fetchall()

        return [self._study_group_thread_summary_from_row(row) for row in rows]

    def get_study_group_chat_for_group(
        self,
        current_user_id: str | UUID | None,
        group_id: str | UUID,
    ) -> dict[str, object] | None:
        with self._connect() as conn:
            resolved_user_id = self._resolve_user_id(conn, current_user_id)
            if not self._is_active_group_member(conn, str(group_id), resolved_user_id):
                return None

            self._ensure_study_group_thread(conn, str(group_id))
            thread_row = self._study_group_chat_row(
                conn,
                resolved_user_id,
                group_id=str(group_id),
            )

        if thread_row is None:
            return None

        return self._study_group_thread_summary_from_row(thread_row)

    def get_study_group_thread_messages(
        self,
        current_user_id: str | UUID | None,
        conversation_id: str | UUID,
    ) -> dict[str, object] | None:
        with self._connect() as conn:
            resolved_user_id = self._resolve_user_id(conn, current_user_id)
            thread_row = self._study_group_chat_row(
                conn,
                resolved_user_id,
                conversation_id=str(conversation_id),
            )
            if thread_row is None:
                return None

            message_rows = conn.execute(
                """
                SELECT m.*, u.first_name, u.last_name, u.scsu_email
                FROM messages m
                LEFT JOIN users u ON u.id = m.sender_id
                WHERE m.conversation_id = ?
                    AND m.status != 'deleted'
                ORDER BY m.sent_at ASC
                """,
                (str(conversation_id),),
            ).fetchall()

        return {
            "conversation": self._study_group_thread_summary_from_row(thread_row),
            "messages": [
                self._message_view_from_row(row, resolved_user_id)
                for row in message_rows
            ],
        }

    def send_study_group_message(
        self,
        current_user_id: str | UUID | None,
        *,
        group_id: str | UUID | None = None,
        conversation_id: str | UUID | None = None,
        content: str = "",
    ) -> dict[str, object] | None:
        content = content.strip()
        if not content:
            return None

        with self._connect() as conn:
            sender_id = self._resolve_user_id(conn, current_user_id)
            thread_row: sqlite3.Row | None = None
            if conversation_id:
                thread_row = self._study_group_chat_row(
                    conn,
                    sender_id,
                    conversation_id=str(conversation_id),
                )
            elif group_id:
                group_id = str(group_id)
                if not self._is_active_group_member(conn, group_id, sender_id):
                    return None
                conversation_id = self._ensure_study_group_thread(conn, group_id)
                thread_row = self._study_group_chat_row(
                    conn,
                    sender_id,
                    conversation_id=conversation_id,
                )
            else:
                return None

            if thread_row is None:
                return None

            conversation_id = thread_row["conversation_id"]
            message = Message(content=content)
            self._insert_message(
                conn,
                str(conversation_id),
                sender_id,
                message,
                ignore_existing=False,
            )

            sent_at = _format_datetime(message.sentAt)
            conn.execute(
                """
                UPDATE conversations
                SET updated_at = ?,
                    last_message_at = ?
                WHERE id = ?
                """,
                (sent_at, sent_at, str(conversation_id)),
            )

            return {
                "conversation_id": str(conversation_id),
                "group_id": thread_row["group_id"],
                "message": message,
            }

    def group_message_notification_data(
        self,
        group_id: str | UUID,
        sender_id: str | UUID,
    ) -> dict[str, object] | None:
        with self._connect() as conn:
            group_row = conn.execute(
                "SELECT title FROM study_groups WHERE id = ?",
                (str(group_id),),
            ).fetchone()
            if group_row is None:
                return None

            sender_row = conn.execute(
                """
                SELECT first_name, last_name, scsu_email
                FROM users
                WHERE id = ?
                """,
                (str(sender_id),),
            ).fetchone()
            sender_name = (
                _display_name(
                    User(
                        scsuEmail=sender_row["scsu_email"],
                        firstName=sender_row["first_name"],
                        lastName=sender_row["last_name"],
                    )
                )
                if sender_row is not None
                else "A group member"
            )

            recipient_rows = conn.execute(
                """
                SELECT DISTINCT u.scsu_email
                FROM group_memberships gm
                JOIN users u ON u.id = gm.member_id
                LEFT JOIN notification_preferences np ON np.user_id = u.id
                WHERE gm.group_id = ?
                    AND gm.status = 'active'
                    AND u.status = 'active'
                    AND u.id != ?
                    AND COALESCE(np.email_enabled, 1) = 1
                    AND COALESCE(np.message_alerts, 1) = 1
                ORDER BY u.scsu_email
                """,
                (str(group_id), str(sender_id)),
            ).fetchall()

        return {
            "group_title": group_row["title"],
            "sender_name": sender_name,
            "recipients": [row["scsu_email"] for row in recipient_rows],
        }

    def send_direct_message(
        self,
        current_user_id: str | UUID | None,
        *,
        recipient_id: str | UUID | None = None,
        conversation_id: str | UUID | None = None,
        content: str = "",
    ) -> dict[str, object] | None:
        content = content.strip()
        if not content:
            return None

        with self._connect() as conn:
            sender_id = self._resolve_user_id(conn, current_user_id)
            if conversation_id:
                conversation_id = str(conversation_id)
                if not self._is_conversation_participant(
                    conn,
                    conversation_id,
                    sender_id,
                ):
                    return None
            elif recipient_id:
                recipient_id = str(recipient_id)
                if recipient_id == sender_id:
                    return None
                if self._active_user_row(conn, recipient_id) is None:
                    return None
                conversation_id = self._ensure_direct_thread(
                    conn,
                    sender_id,
                    recipient_id,
                )
            else:
                return None

            message = Message(content=content)
            self._insert_message(
                conn,
                str(conversation_id),
                sender_id,
                message,
                ignore_existing=False,
            )

            sent_at = _format_datetime(message.sentAt)
            conn.execute(
                """
                UPDATE conversations
                SET updated_at = ?,
                    last_message_at = ?
                WHERE id = ?
                """,
                (sent_at, sent_at, str(conversation_id)),
            )

            return {
                "conversation_id": str(conversation_id),
                "message": message,
            }

    def list_conversations(self) -> list[str]:
        return [
            str(thread["group_title"])
            for thread in self.list_user_study_group_chats(None)
        ]

    def messages_for_conversation(
        self,
        conversation_name: str,
        current_user_id: str | UUID | None,
    ) -> list[dict[str, str]]:
        with self._connect() as conn:
            resolved_user_id = self._resolve_user_id(conn, current_user_id)
            group_id = self._find_study_group_id_by_title(conn, conversation_name)
            if group_id is None:
                return []
            conversation_id = self._study_group_thread_id_for_group(conn, group_id)
            if conversation_id is None:
                return []

        thread = self.get_study_group_thread_messages(resolved_user_id, conversation_id)
        if thread is None:
            return []

        return [
            {
                "sender": "You" if message["is_mine"] else str(message["sender_name"]),
                "text": str(message["content"]),
            }
            for message in thread["messages"]
        ]

    def add_outgoing_message(
        self,
        conversation_name: str,
        content: str,
        current_user_id: str | UUID | None,
    ) -> Message | None:
        with self._connect() as conn:
            group_id = self._find_study_group_id_by_title(conn, conversation_name)

        if group_id is None:
            return None

        result = self.send_study_group_message(
            current_user_id,
            group_id=group_id,
            content=content,
        )
        if result is None:
            return None

        return result["message"]  # type: ignore[return-value]

    def _ensure_parent_directory(self) -> None:
        if self.database_path == ":memory:":
            return

        Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _drop_legacy_message_tables(self, conn: sqlite3.Connection) -> None:
        message_columns = _table_columns(conn, "messages")
        conversation_columns = _table_columns(conn, "conversations")
        has_legacy_messages = "conversation_name" in message_columns
        has_legacy_conversations = (
            "name" in conversation_columns and "id" not in conversation_columns
        )

        if has_legacy_messages or has_legacy_conversations:
            conn.execute("DROP TABLE IF EXISTS messages")
            conn.execute("DROP TABLE IF EXISTS direct_message_threads")
            conn.execute("DROP TABLE IF EXISTS conversation_participants")
            conn.execute("DROP TABLE IF EXISTS conversations")

    def _insert_conversation(
        self,
        conn: sqlite3.Connection,
        conversation_id: str,
        *,
        conversation_type: str = "dm",
        created_at: datetime | None = None,
        last_message_at: datetime | None = None,
        ignore_existing: bool,
    ) -> None:
        created_at = created_at or datetime.now()
        updated_at = last_message_at or created_at
        insert_clause = "INSERT OR IGNORE" if ignore_existing else "INSERT"
        conn.execute(
            f"""
            {insert_clause} INTO conversations (
                id,
                type,
                created_at,
                updated_at,
                last_message_at,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                conversation_id,
                conversation_type,
                _format_datetime(created_at),
                _format_datetime(updated_at),
                _format_datetime(last_message_at),
                "active",
            ),
        )

    def _insert_conversation_participant(
        self,
        conn: sqlite3.Connection,
        conversation_id: str,
        user_id: str,
        *,
        ignore_existing: bool,
    ) -> None:
        insert_clause = "INSERT OR IGNORE" if ignore_existing else "INSERT"
        conn.execute(
            f"""
            {insert_clause} INTO conversation_participants (
                conversation_id,
                user_id,
                joined_at,
                last_read_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                conversation_id,
                user_id,
                _format_datetime(datetime.now()),
                None,
            ),
        )

    def _insert_direct_thread(
        self,
        conn: sqlite3.Connection,
        conversation_id: str,
        first_user_id: str,
        second_user_id: str,
        *,
        ignore_existing: bool,
    ) -> None:
        user_one_id, user_two_id = sorted((first_user_id, second_user_id))
        self._insert_conversation_participant(
            conn,
            conversation_id,
            user_one_id,
            ignore_existing=True,
        )
        self._insert_conversation_participant(
            conn,
            conversation_id,
            user_two_id,
            ignore_existing=True,
        )

        insert_clause = "INSERT OR IGNORE" if ignore_existing else "INSERT"
        conn.execute(
            f"""
            {insert_clause} INTO direct_message_threads (
                conversation_id,
                user_one_id,
                user_two_id
            )
            VALUES (?, ?, ?)
            """,
            (conversation_id, user_one_id, user_two_id),
        )

    def _insert_study_group_thread(
        self,
        conn: sqlite3.Connection,
        conversation_id: str,
        group_id: str,
        *,
        ignore_existing: bool,
    ) -> None:
        insert_clause = "INSERT OR IGNORE" if ignore_existing else "INSERT"
        conn.execute(
            f"""
            {insert_clause} INTO study_group_message_threads (
                conversation_id,
                group_id
            )
            VALUES (?, ?)
            """,
            (conversation_id, group_id),
        )
        self._sync_study_group_thread_participants(conn, conversation_id, group_id)

    def _ensure_direct_thread(
        self,
        conn: sqlite3.Connection,
        first_user_id: str,
        second_user_id: str,
    ) -> str:
        existing_id = self._find_direct_thread_id(conn, first_user_id, second_user_id)
        if existing_id is not None:
            return existing_id

        conversation_id = str(uuid4())
        self._insert_conversation(
            conn,
            conversation_id,
            ignore_existing=False,
        )
        self._insert_direct_thread(
            conn,
            conversation_id,
            first_user_id,
            second_user_id,
            ignore_existing=False,
        )
        return conversation_id

    def _ensure_study_group_threads(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute("SELECT id FROM study_groups").fetchall()
        for row in rows:
            self._ensure_study_group_thread(conn, row["id"])

    def _ensure_study_group_thread(
        self,
        conn: sqlite3.Connection,
        group_id: str,
    ) -> str:
        existing_id = self._study_group_thread_id_for_group(conn, group_id)
        if existing_id is not None:
            self._sync_study_group_thread_participants(conn, existing_id, group_id)
            return existing_id

        group_row = conn.execute(
            "SELECT created_at FROM study_groups WHERE id = ?",
            (group_id,),
        ).fetchone()
        if group_row is None:
            raise RuntimeError("Study group could not be loaded for chat creation")

        conversation_id = str(uuid4())
        self._insert_conversation(
            conn,
            conversation_id,
            conversation_type="study_group",
            created_at=_parse_datetime(group_row["created_at"]),
            ignore_existing=False,
        )
        self._insert_study_group_thread(
            conn,
            conversation_id,
            group_id,
            ignore_existing=False,
        )
        return conversation_id

    def _study_group_thread_id_for_group(
        self,
        conn: sqlite3.Connection,
        group_id: str,
    ) -> str | None:
        row = conn.execute(
            """
            SELECT conversation_id
            FROM study_group_message_threads
            WHERE group_id = ?
            """,
            (group_id,),
        ).fetchone()
        return row["conversation_id"] if row is not None else None

    def _sync_study_group_thread_participants(
        self,
        conn: sqlite3.Connection,
        conversation_id: str,
        group_id: str,
    ) -> None:
        active_member_rows = conn.execute(
            """
            SELECT member_id
            FROM group_memberships
            WHERE group_id = ? AND status = 'active'
            """,
            (group_id,),
        ).fetchall()
        active_member_ids = [row["member_id"] for row in active_member_rows]

        if active_member_ids:
            placeholders = ", ".join("?" for _ in active_member_ids)
            conn.execute(
                f"""
                DELETE FROM conversation_participants
                WHERE conversation_id = ?
                    AND user_id NOT IN ({placeholders})
                """,
                (conversation_id, *active_member_ids),
            )
        else:
            conn.execute(
                "DELETE FROM conversation_participants WHERE conversation_id = ?",
                (conversation_id,),
            )

        for member_id in active_member_ids:
            self._insert_conversation_participant(
                conn,
                conversation_id,
                member_id,
                ignore_existing=True,
            )

    def _find_direct_thread_id(
        self,
        conn: sqlite3.Connection,
        first_user_id: str,
        second_user_id: str,
    ) -> str | None:
        user_one_id, user_two_id = sorted((first_user_id, second_user_id))
        row = conn.execute(
            """
            SELECT conversation_id
            FROM direct_message_threads
            WHERE user_one_id = ? AND user_two_id = ?
            """,
            (user_one_id, user_two_id),
        ).fetchone()
        return row["conversation_id"] if row is not None else None

    def _is_conversation_participant(
        self,
        conn: sqlite3.Connection,
        conversation_id: str,
        user_id: str,
    ) -> bool:
        row = conn.execute(
            """
            SELECT 1
            FROM conversation_participants
            WHERE conversation_id = ? AND user_id = ?
            """,
            (conversation_id, user_id),
        ).fetchone()
        return row is not None

    def _active_user_row(
        self,
        conn: sqlite3.Connection,
        user_id: str,
    ) -> sqlite3.Row | None:
        return conn.execute(
            """
            SELECT *
            FROM users
            WHERE id = ? AND status = 'active'
            """,
            (user_id,),
        ).fetchone()

    def _is_active_group_member(
        self,
        conn: sqlite3.Connection,
        group_id: str,
        user_id: str,
    ) -> bool:
        row = conn.execute(
            """
            SELECT 1
            FROM group_memberships
            WHERE group_id = ?
                AND member_id = ?
                AND status = 'active'
            """,
            (group_id, user_id),
        ).fetchone()
        return row is not None

    def _dm_thread_row(
        self,
        conn: sqlite3.Connection,
        current_user_id: str,
        conversation_id: str,
    ) -> sqlite3.Row | None:
        return conn.execute(
            """
            SELECT
                c.id AS conversation_id,
                c.last_message_at,
                other.id AS participant_id,
                other.scsu_email,
                other.first_name,
                other.last_name,
                other.major,
                latest.content AS last_message,
                latest.sent_at AS last_sent_at
            FROM conversations c
            JOIN conversation_participants mine
                ON mine.conversation_id = c.id
                AND mine.user_id = ?
            JOIN direct_message_threads d
                ON d.conversation_id = c.id
            JOIN users other
                ON other.id = CASE
                    WHEN d.user_one_id = ? THEN d.user_two_id
                    ELSE d.user_one_id
                END
            LEFT JOIN messages latest
                ON latest.id = (
                    SELECT m.id
                    FROM messages m
                    WHERE m.conversation_id = c.id
                        AND m.status != 'deleted'
                    ORDER BY m.sent_at DESC
                    LIMIT 1
                )
            WHERE c.id = ?
                AND c.status = 'active'
            """,
            (current_user_id, current_user_id, conversation_id),
        ).fetchone()

    def _study_group_chat_row(
        self,
        conn: sqlite3.Connection,
        current_user_id: str,
        *,
        conversation_id: str | None = None,
        group_id: str | None = None,
    ) -> sqlite3.Row | None:
        if conversation_id is None and group_id is None:
            return None

        if conversation_id is not None:
            where_clause = "c.id = ?"
            where_value = conversation_id
        else:
            where_clause = "g.id = ?"
            where_value = group_id

        return conn.execute(
            f"""
            SELECT
                c.id AS conversation_id,
                c.last_message_at,
                g.id AS group_id,
                g.title AS group_title,
                g.subject AS group_subject,
                g.modality AS group_modality,
                g.location AS group_location,
                g.meeting_link AS group_meeting_link,
                g.status AS group_status,
                latest.content AS last_message,
                latest.sent_at AS last_sent_at,
                (
                    SELECT COUNT(*)
                    FROM group_memberships active_members
                    WHERE active_members.group_id = g.id
                        AND active_members.status = 'active'
                ) AS member_count
            FROM conversations c
            JOIN study_group_message_threads group_thread
                ON group_thread.conversation_id = c.id
            JOIN study_groups g
                ON g.id = group_thread.group_id
            JOIN group_memberships mine
                ON mine.group_id = g.id
                AND mine.member_id = ?
                AND mine.status = 'active'
            LEFT JOIN messages latest
                ON latest.id = (
                    SELECT m.id
                    FROM messages m
                    WHERE m.conversation_id = c.id
                        AND m.status != 'deleted'
                    ORDER BY m.sent_at DESC
                    LIMIT 1
                )
            WHERE {where_clause}
                AND c.status = 'active'
            """,
            (current_user_id, where_value),
        ).fetchone()

    def _user_search_result_from_row(self, row: sqlite3.Row) -> dict[str, str]:
        full_name = _display_name(
            User(
                id=UUID(row["id"]),
                scsuEmail=row["scsu_email"],
                firstName=row["first_name"],
                lastName=row["last_name"],
                major=row["major"],
            )
        )
        return {
            "id": row["id"],
            "name": full_name,
            "email": row["scsu_email"],
            "major": row["major"],
        }

    def _thread_summary_from_row(self, row: sqlite3.Row) -> dict[str, str]:
        name = _display_name(
            User(
                id=UUID(row["participant_id"]),
                scsuEmail=row["scsu_email"],
                firstName=row["first_name"],
                lastName=row["last_name"],
                major=row["major"],
            )
        )
        return {
            "id": row["conversation_id"],
            "participant_id": row["participant_id"],
            "participant_name": name,
            "participant_email": row["scsu_email"],
            "participant_major": row["major"],
            "last_message": row["last_message"] or "",
            "last_sent_at": row["last_sent_at"] or "",
        }

    def _study_group_thread_summary_from_row(
        self,
        row: sqlite3.Row,
    ) -> dict[str, object]:
        return {
            "id": row["conversation_id"],
            "conversation_id": row["conversation_id"],
            "group_id": row["group_id"],
            "group_title": row["group_title"],
            "group_subject": row["group_subject"],
            "group_modality": row["group_modality"],
            "group_location": row["group_location"],
            "group_meeting_link": row["group_meeting_link"],
            "group_status": row["group_status"],
            "member_count": row["member_count"] or 0,
            "last_message": row["last_message"] or "",
            "last_sent_at": row["last_sent_at"] or "",
        }

    def _message_view_from_row(
        self,
        row: sqlite3.Row,
        current_user_id: str,
    ) -> dict[str, object]:
        sender_name = "Unknown sender"
        if row["sender_id"]:
            sender_name = _display_name(
                User(
                    id=UUID(row["sender_id"]),
                    scsuEmail=row["scsu_email"] or "",
                    firstName=row["first_name"] or "",
                    lastName=row["last_name"] or "",
                )
            )

        return {
            "id": row["id"],
            "sender_id": row["sender_id"] or "",
            "sender_name": sender_name,
            "content": row["content"],
            "sent_at": row["sent_at"],
            "is_mine": row["sender_id"] == current_user_id,
        }

    def _seed_defaults(self, conn: sqlite3.Connection) -> None:
        users = {
            "test": User(
                id=_stable_uuid("user:test"),
                scsuEmail=DEFAULT_USER_EMAIL,
                passwordHash=generate_password_hash("1234"),
                firstName="Test",
                lastName="User",
                major="Computer Science",
                interests=["Flask", "UI design", "algorithms"],
                bio=(
                    "Student interested in web development, Python, and building "
                    "useful campus tools."
                ),
                contactInfo="test@southernct.edu",
            ),
            "john": User(
                id=_stable_uuid("user:john-smith"),
                scsuEmail="john.smith@southernct.edu",
                firstName="John",
                lastName="Smith",
                major="Computer Science",
            ),
            "sarah": User(
                id=_stable_uuid("user:sarah-lee"),
                scsuEmail="sarah.lee@southernct.edu",
                firstName="Sarah",
                lastName="Lee",
                major="Mathematics",
            ),
            "alex": User(
                id=_stable_uuid("user:alex-mitchell"),
                scsuEmail="alex.mitchell@southernct.edu",
                firstName="Alex",
                lastName="Mitchell",
                major="Computer Science",
            ),
            "priya": User(
                id=_stable_uuid("user:priya-nair"),
                scsuEmail="priya.nair@southernct.edu",
                firstName="Priya",
                lastName="Nair",
                major="Biology",
            ),
            "marcus": User(
                id=_stable_uuid("user:marcus-reed"),
                scsuEmail="marcus.reed@southernct.edu",
                firstName="Marcus",
                lastName="Reed",
                major="History",
            ),
            "lena": User(
                id=_stable_uuid("user:lena-ortiz"),
                scsuEmail="lena.ortiz@southernct.edu",
                firstName="Lena",
                lastName="Ortiz",
                major="Chemistry",
            ),
        }

        for user in users.values():
            self._insert_user(conn, user, ignore_existing=True)

        groups = [
            StudyGroup(
                id=_stable_uuid("group:software-design-studio"),
                title="Software Design Studio",
                subject="CSC 330 - Software Engineering",
                description=(
                    "Peer review for project milestones, UML diagrams, Flask routes, "
                    "and test planning before the next sprint submission."
                ),
                startAt=datetime(2026, 5, 4, 16, 0),
                endAt=datetime(2026, 5, 4, 17, 30),
                modality="In person",
                location="Buley Library, Room 205",
                maxMembers=8,
                creator=users["alex"],
            ),
            StudyGroup(
                id=_stable_uuid("group:calculus-problem-session"),
                title="Calculus II Problem Session",
                subject="MAT 221 - Calculus II",
                description=(
                    "Structured practice on integration strategies, sequences, and "
                    "series with time reserved for exam review questions."
                ),
                startAt=datetime(2026, 5, 5, 11, 0),
                endAt=datetime(2026, 5, 5, 12, 15),
                modality="In person",
                location="Engleman Hall, A112",
                maxMembers=6,
                creator=users["test"],
            ),
            StudyGroup(
                id=_stable_uuid("group:anatomy-lab-review"),
                title="Anatomy Lab Review",
                subject="BIO 211 - Human Anatomy and Physiology",
                description=(
                    "Lab practical preparation using diagrams, terminology drills, "
                    "and collaborative review of recent lecture objectives."
                ),
                startAt=datetime(2026, 5, 6, 18, 0),
                endAt=datetime(2026, 5, 6, 19, 15),
                modality="Hybrid",
                location="Jennings Hall, Lab 148",
                meetingLink="https://example.edu/scsu-bio211-review",
                maxMembers=10,
                creator=users["priya"],
            ),
            StudyGroup(
                id=_stable_uuid("group:research-writing-circle"),
                title="Research Writing Circle",
                subject="HIS 112 - U.S. History Since 1877",
                description=(
                    "Source evaluation, thesis refinement, and citation review for "
                    "final research papers in a moderated virtual session."
                ),
                startAt=datetime(2026, 5, 7, 20, 0),
                endAt=datetime(2026, 5, 7, 21, 0),
                modality="Virtual",
                meetingLink="https://example.edu/scsu-history-circle",
                maxMembers=0,
                creator=users["marcus"],
            ),
            StudyGroup(
                id=_stable_uuid("group:general-chemistry-lab-prep"),
                title="General Chemistry Lab Prep",
                subject="CHE 120 - General Chemistry I",
                description=(
                    "Pre-lab calculations, safety review, and discussion of the "
                    "experiment procedure before Friday's lab block."
                ),
                startAt=datetime(2026, 5, 8, 9, 30),
                endAt=datetime(2026, 5, 8, 10, 30),
                modality="In person",
                location="Jennings Hall, Room 231",
                maxMembers=5,
                creator=users["lena"],
            ),
        ]

        for group in groups:
            self._insert_study_group(conn, group, ignore_existing=True)

        member_sets = [
            (groups[0], [users["test"], users["alex"], users["priya"]]),
            (groups[1], [users["test"], users["marcus"]]),
            (groups[2], [users["priya"], users["lena"], users["marcus"], users["alex"]]),
            (groups[3], [users["marcus"], users["test"], users["alex"]]),
            (groups[4], [users["lena"], users["priya"]]),
        ]

        for group, members in member_sets:
            for member in members:
                membership = GroupMembership(
                    id=_stable_uuid(f"membership:{member.id}:{group.id}"),
                    member=member,
                    group=group,
                )
                self._insert_membership(conn, membership, ignore_existing=True)

        group_conversation_ids: dict[str, str] = {}
        for group in groups:
            group_conversation_id = str(
                _stable_uuid(f"conversation:study-group:{group.id}")
            )
            group_conversation_ids[str(group.id)] = group_conversation_id
            self._insert_conversation(
                conn,
                group_conversation_id,
                conversation_type="study_group",
                created_at=group.createdAt,
                ignore_existing=True,
            )
            self._insert_study_group_thread(
                conn,
                group_conversation_id,
                str(group.id),
                ignore_existing=True,
            )

        software_conversation_id = group_conversation_ids[str(groups[0].id)]
        software_last_message_at = datetime(2026, 5, 4, 15, 15)
        self._insert_message(
            conn,
            software_conversation_id,
            str(users["alex"].id),
            Message(
                id=_stable_uuid("message:software-design:incoming-1"),
                content="I added the route test checklist for tonight.",
                sentAt=datetime(2026, 5, 4, 15, 0),
            ),
            ignore_existing=True,
        )
        self._insert_message(
            conn,
            software_conversation_id,
            str(users["test"].id),
            Message(
                id=_stable_uuid("message:software-design:outgoing-1"),
                content="I will review the Flask handlers before we meet.",
                sentAt=software_last_message_at,
            ),
            ignore_existing=True,
        )
        conn.execute(
            """
            UPDATE conversations
            SET updated_at = ?,
                last_message_at = ?
            WHERE id = ?
            """,
            (
                _format_datetime(software_last_message_at),
                _format_datetime(software_last_message_at),
                software_conversation_id,
            ),
        )

        calculus_conversation_id = group_conversation_ids[str(groups[1].id)]
        calculus_last_message_at = datetime(2026, 5, 5, 9, 20)
        self._insert_message(
            conn,
            calculus_conversation_id,
            str(users["test"].id),
            Message(
                id=_stable_uuid("message:calculus:outgoing-1"),
                content="Bring any integration by parts questions to the session.",
                sentAt=calculus_last_message_at,
            ),
            ignore_existing=True,
        )
        conn.execute(
            """
            UPDATE conversations
            SET updated_at = ?,
                last_message_at = ?
            WHERE id = ?
            """,
            (
                _format_datetime(calculus_last_message_at),
                _format_datetime(calculus_last_message_at),
                calculus_conversation_id,
            ),
        )

        for group in (groups[0], groups[3]):
            self._insert_favorite(conn, users["test"], group)

        john_conversation_id = str(_stable_uuid("conversation:test-john-smith"))
        john_created_at = datetime(2026, 5, 4, 10, 0)
        self._insert_conversation(
            conn,
            john_conversation_id,
            created_at=john_created_at,
            last_message_at=datetime(2026, 5, 4, 10, 5),
            ignore_existing=True,
        )
        self._insert_direct_thread(
            conn,
            john_conversation_id,
            str(users["test"].id),
            str(users["john"].id),
            ignore_existing=True,
        )
        self._insert_message(
            conn,
            john_conversation_id,
            str(users["john"].id),
            Message(
                id=_stable_uuid("message:john:incoming-1"),
                content="Hey, are we meeting today?",
                sentAt=datetime(2026, 5, 4, 10, 0),
            ),
            ignore_existing=True,
        )
        self._insert_message(
            conn,
            john_conversation_id,
            str(users["test"].id),
            Message(
                id=_stable_uuid("message:john:outgoing-1"),
                content="Yes, at 3 PM in the library.",
                sentAt=datetime(2026, 5, 4, 10, 5),
            ),
            ignore_existing=True,
        )

    def _insert_user(
        self,
        conn: sqlite3.Connection,
        user: User,
        *,
        ignore_existing: bool,
    ) -> None:
        insert_clause = "INSERT OR IGNORE" if ignore_existing else "INSERT"
        conn.execute(
            f"""
            {insert_clause} INTO users (
                id,
                scsu_email,
                password_hash,
                first_name,
                last_name,
                major,
                interests,
                bio,
                profile_image_url,
                contact_info,
                status,
                role,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(user.id),
                normalize_email(user.scsuEmail),
                user.passwordHash,
                user.firstName,
                user.lastName,
                user.major,
                json.dumps(user.interests),
                user.bio,
                user.profileImageUrl,
                user.contactInfo,
                user.status,
                user.role,
                _format_datetime(user.createdAt),
            ),
        )

        preference = user.preference or NotificationPreference(user=user)
        conn.execute(
            """
            INSERT OR IGNORE INTO notification_preferences (
                user_id,
                email_enabled,
                in_app_enabled,
                message_alerts,
                reminder_alerts,
                group_update_alerts
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(user.id),
                int(preference.emailEnabled),
                int(preference.inAppEnabled),
                int(preference.messageAlerts),
                int(preference.reminderAlerts),
                int(preference.groupUpdateAlerts),
            ),
        )

    def _insert_study_group(
        self,
        conn: sqlite3.Connection,
        group: StudyGroup,
        *,
        ignore_existing: bool,
    ) -> None:
        insert_clause = "INSERT OR IGNORE" if ignore_existing else "INSERT"
        conn.execute(
            f"""
            {insert_clause} INTO study_groups (
                id,
                title,
                subject,
                description,
                start_at,
                end_at,
                modality,
                location,
                meeting_link,
                max_members,
                status,
                created_at,
                creator_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(group.id),
                group.title,
                group.subject,
                group.description,
                _format_datetime(group.startAt),
                _format_datetime(group.endAt),
                group.modality,
                group.location,
                group.meetingLink,
                group.maxMembers,
                group.status,
                _format_datetime(group.createdAt),
                str(group.creator.id) if group.creator else None,
            ),
        )

    def _insert_membership(
        self,
        conn: sqlite3.Connection,
        membership: GroupMembership,
        *,
        ignore_existing: bool,
    ) -> None:
        insert_clause = "INSERT OR IGNORE" if ignore_existing else "INSERT"
        conn.execute(
            f"""
            {insert_clause} INTO group_memberships (
                id,
                member_id,
                group_id,
                joined_at,
                role,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(membership.id),
                str(membership.member.id) if membership.member else None,
                str(membership.group.id) if membership.group else None,
                _format_datetime(membership.joinedAt),
                membership.role,
                membership.status,
            ),
        )

    def _insert_favorite(
        self,
        conn: sqlite3.Connection,
        user: User,
        group: StudyGroup,
    ) -> None:
        conn.execute(
            """
            INSERT OR IGNORE INTO favorite_study_groups (user_id, group_id)
            VALUES (?, ?)
            """,
            (str(user.id), str(group.id)),
        )

    def _insert_message(
        self,
        conn: sqlite3.Connection,
        conversation_id: str,
        sender_id: str,
        message: Message,
        *,
        ignore_existing: bool,
    ) -> None:
        insert_clause = "INSERT OR IGNORE" if ignore_existing else "INSERT"
        conn.execute(
            f"""
            {insert_clause} INTO messages (
                id,
                conversation_id,
                sender_id,
                content,
                sent_at,
                edited_at,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(message.id),
                conversation_id,
                sender_id,
                message.content,
                _format_datetime(message.sentAt),
                _format_datetime(message.editedAt),
                message.status,
            ),
        )

    def _load_users(self, conn: sqlite3.Connection) -> dict[str, User]:
        rows = conn.execute("SELECT * FROM users ORDER BY first_name, last_name").fetchall()
        users = {row["id"]: self._user_from_row(row) for row in rows}
        self._apply_preferences(conn, users)
        return users

    def _load_study_groups(
        self,
        conn: sqlite3.Connection,
        users: dict[str, User],
    ) -> dict[str, StudyGroup]:
        rows = conn.execute(
            """
            SELECT *
            FROM study_groups
            ORDER BY COALESCE(start_at, created_at), title
            """
        ).fetchall()

        groups: dict[str, StudyGroup] = {}
        for row in rows:
            creator = users.get(row["creator_id"]) if row["creator_id"] else None
            group = StudyGroup(
                id=UUID(row["id"]),
                title=row["title"],
                subject=row["subject"],
                description=row["description"],
                startAt=_parse_datetime(row["start_at"]),
                endAt=_parse_datetime(row["end_at"]),
                modality=row["modality"],
                location=row["location"],
                meetingLink=row["meeting_link"],
                maxMembers=row["max_members"],
                status=row["status"],
                createdAt=_parse_datetime(row["created_at"]) or datetime.now(),
                creator=creator,
            )
            groups[row["id"]] = group

        return groups

    def _load_memberships(
        self,
        conn: sqlite3.Connection,
        users: dict[str, User],
        groups: dict[str, StudyGroup],
    ) -> None:
        rows = conn.execute("SELECT * FROM group_memberships").fetchall()
        for row in rows:
            member = users.get(row["member_id"]) if row["member_id"] else None
            group = groups.get(row["group_id"]) if row["group_id"] else None
            GroupMembership(
                id=UUID(row["id"]),
                member=member,
                group=group,
                joinedAt=_parse_datetime(row["joined_at"]) or datetime.now(),
                role=row["role"],
                status=row["status"],
            )

    def _load_favorites(
        self,
        conn: sqlite3.Connection,
        users: dict[str, User],
        groups: dict[str, StudyGroup],
    ) -> None:
        rows = conn.execute("SELECT * FROM favorite_study_groups").fetchall()
        for row in rows:
            user = users.get(row["user_id"])
            group = groups.get(row["group_id"])
            if user is None or group is None:
                continue

            if group not in user.favoriteStudyGroups:
                user.favoriteStudyGroups.append(group)
            if user not in group.favoritedBy:
                group.favoritedBy.append(user)

    def _user_from_row(self, row: sqlite3.Row) -> User:
        return User(
            id=UUID(row["id"]),
            scsuEmail=row["scsu_email"],
            passwordHash=row["password_hash"],
            firstName=row["first_name"],
            lastName=row["last_name"],
            major=row["major"],
            interests=_parse_json_list(row["interests"]),
            bio=row["bio"],
            profileImageUrl=row["profile_image_url"],
            contactInfo=row["contact_info"],
            status=row["status"],
            role=row["role"],
            createdAt=_parse_datetime(row["created_at"]) or datetime.now(),
        )

    def _apply_preferences(
        self,
        conn: sqlite3.Connection,
        users: dict[str, User],
    ) -> None:
        rows = conn.execute("SELECT * FROM notification_preferences").fetchall()
        for row in rows:
            user = users.get(row["user_id"])
            if user is not None:
                user.preference = self._preference_from_row(row, user)

    def _apply_preference(self, conn: sqlite3.Connection, user: User) -> None:
        row = conn.execute(
            "SELECT * FROM notification_preferences WHERE user_id = ?",
            (str(user.id),),
        ).fetchone()
        if row is not None:
            user.preference = self._preference_from_row(row, user)

    def _preference_from_row(
        self,
        row: sqlite3.Row,
        user: User,
    ) -> NotificationPreference:
        return NotificationPreference(
            user=user,
            emailEnabled=bool(row["email_enabled"]),
            inAppEnabled=bool(row["in_app_enabled"]),
            messageAlerts=bool(row["message_alerts"]),
            reminderAlerts=bool(row["reminder_alerts"]),
            groupUpdateAlerts=bool(row["group_update_alerts"]),
        )

    def _resolve_user_id(
        self,
        conn: sqlite3.Connection,
        user_id: str | UUID | None,
    ) -> str:
        if user_id:
            row = conn.execute(
                "SELECT id FROM users WHERE id = ?",
                (str(user_id),),
            ).fetchone()
            if row is not None:
                return row["id"]

        row = conn.execute(
            "SELECT id FROM users WHERE scsu_email = ?",
            (DEFAULT_USER_EMAIL,),
        ).fetchone()
        if row is not None:
            return row["id"]

        row = conn.execute("SELECT id FROM users ORDER BY created_at LIMIT 1").fetchone()
        if row is None:
            raise RuntimeError("No users are available in the SQLite database")

        return row["id"]

    def _find_user_id_by_display_name(
        self,
        conn: sqlite3.Connection,
        display_name: str,
    ) -> str | None:
        rows = conn.execute("SELECT id, first_name, last_name FROM users").fetchall()
        for row in rows:
            full_name = f"{row['first_name']} {row['last_name']}".strip()
            if full_name == display_name:
                return row["id"]

        return None

    def _find_study_group_id_by_title(
        self,
        conn: sqlite3.Connection,
        title: str,
    ) -> str | None:
        normalized_title = title.casefold()
        rows = conn.execute("SELECT id, title FROM study_groups").fetchall()
        for row in rows:
            if row["title"].casefold() == normalized_title:
                return row["id"]

        return None


def _stable_uuid(name: str) -> UUID:
    return uuid5(APP_NAMESPACE, name)


def _format_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None

    return value.isoformat(timespec="seconds")


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    return datetime.fromisoformat(value)


def _parse_json_list(value: str | None) -> list[str]:
    if not value:
        return []

    try:
        decoded = json.loads(value)
    except json.JSONDecodeError:
        return []

    if not isinstance(decoded, list):
        return []

    return [str(item) for item in decoded]


def _table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row["name"] for row in rows}


def _display_name(user: User | None) -> str:
    if user is None:
        return ""

    return user.getFullName() or user.scsuEmail
