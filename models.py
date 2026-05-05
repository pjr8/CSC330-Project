from __future__ import annotations

from datetime import datetime

from db import db


favorite_study_groups = db.Table(
    "favorite_study_groups",
    db.Column("user_id", db.Integer, db.ForeignKey("users.id"), primary_key=True),
    db.Column(
        "study_group_id",
        db.Integer,
        db.ForeignKey("study_groups.id"),
        primary_key=True,
    ),
)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    scsuEmail = db.Column(db.String(255), unique=True, nullable=False)
    passwordHash = db.Column(db.String(255), nullable=False)
    firstName = db.Column(db.String(100), nullable=False)
    lastName = db.Column(db.String(100), nullable=False)
    major = db.Column(db.String(150), default="", nullable=False)
    interests = db.Column(db.JSON, default=list, nullable=False)
    bio = db.Column(db.Text, default="", nullable=False)
    contactInfo = db.Column(db.Text, default="", nullable=False)
    profileImageUrl = db.Column(db.String(255), default="", nullable=False)
    status = db.Column(db.String(50), default="active", nullable=False)
    role = db.Column(db.String(50), default="student", nullable=False)
    createdAt = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    favoriteStudyGroups = db.relationship(
        "StudyGroup",
        secondary=favorite_study_groups,
        back_populates="favoritedBy",
    )
    memberships = db.relationship(
        "GroupMembership",
        back_populates="member",
        cascade="all, delete-orphan",
        foreign_keys="GroupMembership.member_id",
    )
    createdStudyGroups = db.relationship(
        "StudyGroup",
        back_populates="creator",
        cascade="all, delete-orphan",
        foreign_keys="StudyGroup.creator_id",
    )
    sentMessages = db.relationship(
        "Message",
        back_populates="sender",
        cascade="all, delete-orphan",
        foreign_keys="Message.sender_id",
    )
    receivedMessages = db.relationship(
        "Message",
        back_populates="recipient",
        cascade="all, delete-orphan",
        foreign_keys="Message.recipient_id",
    )

    def getFullName(self) -> str:
        return f"{self.firstName} {self.lastName}".strip()

    def updateProfile(self, **updates: object) -> None:
        editable_fields = {
            "scsuEmail",
            "passwordHash",
            "firstName",
            "lastName",
            "major",
            "interests",
            "bio",
            "contactInfo",
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


class StudyGroup(db.Model):
    __tablename__ = "study_groups"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    subject = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, default="", nullable=False)
    startAt = db.Column(db.DateTime, nullable=True)
    endAt = db.Column(db.DateTime, nullable=True)
    modality = db.Column(db.String(50), default="", nullable=False)
    location = db.Column(db.String(255), default="", nullable=False)
    meetingLink = db.Column(db.String(255), default="", nullable=False)
    maxMembers = db.Column(db.Integer, default=0, nullable=False)
    status = db.Column(db.String(50), default="open", nullable=False)
    createdAt = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    creator_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    creator = db.relationship(
        "User",
        back_populates="createdStudyGroups",
        foreign_keys=[creator_id],
    )
    memberships = db.relationship(
        "GroupMembership",
        back_populates="group",
        cascade="all, delete-orphan",
    )
    favoritedBy = db.relationship(
        "User",
        secondary=favorite_study_groups,
        back_populates="favoriteStudyGroups",
    )

    def updateDetails(self, **updates: object) -> None:
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


class GroupMembership(db.Model):
    __tablename__ = "group_memberships"

    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey("study_groups.id"), nullable=False)
    joinedAt = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    role = db.Column(db.String(50), default="member", nullable=False)
    status = db.Column(db.String(50), default="active", nullable=False)

    member = db.relationship(
        "User",
        back_populates="memberships",
        foreign_keys=[member_id],
    )
    group = db.relationship("StudyGroup", back_populates="memberships")

    def leave(self) -> None:
        self.status = "left"

    def changeRole(self, role: str) -> None:
        self.role = role

    def remove(self) -> None:
        self.status = "removed"


class Message(db.Model):
    __tablename__ = "messages"

    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    content = db.Column(db.Text, default="", nullable=False)
    sentAt = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    editedAt = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(50), default="sent", nullable=False)

    sender = db.relationship(
        "User",
        back_populates="sentMessages",
        foreign_keys=[sender_id],
    )
    recipient = db.relationship(
        "User",
        back_populates="receivedMessages",
        foreign_keys=[recipient_id],
    )

    def edit(self, content: str) -> None:
        self.content = content
        self.editedAt = datetime.utcnow()

    def softDelete(self) -> None:
        self.status = "deleted"
        self.content = ""


__all__ = ["GroupMembership", "Message", "StudyGroup", "User", "favorite_study_groups"]
