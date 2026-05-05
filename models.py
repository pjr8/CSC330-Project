from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4


DateTime = datetime


def _contains_identity(items: list[Any], target: Any) -> bool:
    return any(item is target for item in items)


@dataclass
class User:
    id: UUID = field(default_factory=uuid4)
    scsuEmail: str = ""
    passwordHash: str = ""
    firstName: str = ""
    lastName: str = ""
    major: str = ""
    interests: list[str] = field(default_factory=list)
    bio: str = ""
    profileImageUrl: str = ""
    status: str = "active"
    role: str = "student"
    createdAt: DateTime = field(default_factory=datetime.now)
    preference: NotificationPreference | None = None
    favoriteStudyGroups: list[StudyGroup] = field(default_factory=list)
    memberships: list[GroupMembership] = field(default_factory=list)
    notifications: list[Notification] = field(default_factory=list)
    createdStudyGroups: list[StudyGroup] = field(default_factory=list)
    reviews: list[Review] = field(default_factory=list)
    reports: list[Report] = field(default_factory=list)
    sentMessages: list[Message] = field(default_factory=list)
    receivedMessages: list[Message] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.preference is None:
            self.preference = NotificationPreference(user=self)
        elif self.preference.user is not self:
            self.preference.user = self

    def getFullName(self) -> str:
        return f"{self.firstName} {self.lastName}".strip()

    def updateProfile(self, **updates: Any) -> None:
        editable_fields = {
            "scsuEmail",
            "passwordHash",
            "firstName",
            "lastName",
            "major",
            "interests",
            "bio",
            "profileImageUrl",
            "status",
            "role",
        }
        for field_name, value in updates.items():
            if field_name not in editable_fields:
                raise AttributeError(f"{field_name} cannot be updated on User")
            setattr(self, field_name, value)

    def deactivate(self) -> None:
        self.status = "inactive"


@dataclass
class GroupMembership:
    id: UUID = field(default_factory=uuid4)
    member: User | None = None
    group: StudyGroup | None = None
    joinedAt: DateTime = field(default_factory=datetime.now)
    role: str = "member"
    status: str = "active"

    def __post_init__(self) -> None:
        if self.member is not None and not _contains_identity(
            self.member.memberships, self
        ):
            self.member.memberships.append(self)
        if self.group is not None and not _contains_identity(self.group.memberships, self):
            self.group.memberships.append(self)

    def leave(self) -> None:
        self.status = "left"

    def changeRole(self, role: str) -> None:
        self.role = role

    def remove(self) -> None:
        self.status = "removed"


@dataclass
class StudyGroup:
    id: UUID = field(default_factory=uuid4)
    title: str = ""
    subject: str = ""
    description: str = ""
    startAt: DateTime | None = None
    endAt: DateTime | None = None
    modality: str = ""
    location: str = ""
    meetingLink: str = ""
    maxMembers: int = 0
    status: str = "open"
    createdAt: DateTime = field(default_factory=datetime.now)
    creator: User | None = None
    memberships: list[GroupMembership] = field(default_factory=list)
    reviews: list[Review] = field(default_factory=list)
    favoritedBy: list[User] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.creator is not None and not _contains_identity(
            self.creator.createdStudyGroups, self
        ):
            self.creator.createdStudyGroups.append(self)

    def updateDetails(self, **updates: Any) -> None:
        editable_fields = {
            "title",
            "subject",
            "description",
            "startAt",
            "endAt",
            "modality",
            "location",
            "meetingLink",
            "maxMembers",
            "status",
        }
        for field_name, value in updates.items():
            if field_name not in editable_fields:
                raise AttributeError(f"{field_name} cannot be updated on StudyGroup")
            setattr(self, field_name, value)

    def close(self) -> None:
        self.status = "closed"

    def hasAvailableSeat(self) -> bool:
        if self.maxMembers <= 0:
            return True
        active_members = sum(
            1 for membership in self.memberships if membership.status == "active"
        )
        return active_members < self.maxMembers


@dataclass
class Review:
    id: UUID = field(default_factory=uuid4)
    reviewer: User | None = None
    group: StudyGroup | None = None
    rating: int = 0
    comment: str = ""
    createdAt: DateTime = field(default_factory=datetime.now)
    updatedAt: DateTime = field(default_factory=datetime.now)
    status: str = "active"

    def __post_init__(self) -> None:
        if self.reviewer is not None and not _contains_identity(
            self.reviewer.reviews, self
        ):
            self.reviewer.reviews.append(self)
        if self.group is not None and not _contains_identity(self.group.reviews, self):
            self.group.reviews.append(self)

    def edit(self, rating: int, comment: str) -> None:
        self.rating = rating
        self.comment = comment
        self.updatedAt = datetime.now()

    def delete(self) -> None:
        self.status = "deleted"


@dataclass
class Report:
    id: UUID = field(default_factory=uuid4)
    reporter: User | None = None
    targetType: str = ""
    targetId: UUID | None = None
    reason: str = ""
    details: str = ""
    status: str = "open"
    createdAt: DateTime = field(default_factory=datetime.now)
    resolvedAt: DateTime | None = None

    def __post_init__(self) -> None:
        if self.reporter is not None and not _contains_identity(
            self.reporter.reports, self
        ):
            self.reporter.reports.append(self)

    def resolve(self) -> None:
        self.status = "resolved"
        self.resolvedAt = datetime.now()

    def dismiss(self) -> None:
        self.status = "dismissed"
        self.resolvedAt = datetime.now()


@dataclass
class Message:
    id: UUID = field(default_factory=uuid4)
    sender: User | None = None
    recipient: User | None = None
    content: str = ""
    sentAt: DateTime = field(default_factory=datetime.now)
    editedAt: DateTime | None = None
    status: str = "sent"

    def __post_init__(self) -> None:
        if self.sender is not None and not _contains_identity(
            self.sender.sentMessages, self
        ):
            self.sender.sentMessages.append(self)
        if self.recipient is not None and not _contains_identity(
            self.recipient.receivedMessages, self
        ):
            self.recipient.receivedMessages.append(self)

    def edit(self, content: str) -> None:
        self.content = content
        self.editedAt = datetime.now()

    def softDelete(self) -> None:
        self.status = "deleted"
        self.content = ""


@dataclass
class NotificationPreference:
    user: User | None = None
    emailEnabled: bool = True
    inAppEnabled: bool = True
    messageAlerts: bool = True
    reminderAlerts: bool = True
    groupUpdateAlerts: bool = True

    def updatePreferences(self, **updates: bool) -> None:
        editable_fields = {
            "emailEnabled",
            "inAppEnabled",
            "messageAlerts",
            "reminderAlerts",
            "groupUpdateAlerts",
        }
        for field_name, value in updates.items():
            if field_name not in editable_fields:
                raise AttributeError(
                    f"{field_name} cannot be updated on NotificationPreference"
                )
            setattr(self, field_name, bool(value))


@dataclass
class Notification:
    id: UUID = field(default_factory=uuid4)
    recipient: User | None = None
    message: str = ""
    type: str = ""
    relatedTargetType: str | None = None
    relatedTargetId: UUID | None = None
    createdAt: DateTime = field(default_factory=datetime.now)
    readAt: DateTime | None = None

    def __post_init__(self) -> None:
        if self.recipient is not None and not _contains_identity(
            self.recipient.notifications, self
        ):
            self.recipient.notifications.append(self)

    def markAsRead(self) -> None:
        self.readAt = datetime.now()


__all__ = [
    "GroupMembership",
    "Message",
    "Notification",
    "NotificationPreference",
    "Report",
    "Review",
    "StudyGroup",
    "User",
]