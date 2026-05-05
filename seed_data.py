from __future__ import annotations

from datetime import datetime

from werkzeug.security import generate_password_hash

from db import db
from models import GroupMembership, Message, StudyGroup, User


DEMO_EMAIL = "test@southernct.edu"


def seed_database() -> None:
    if User.query.first() is not None:
        return

    current_user = User(
        scsuEmail=DEMO_EMAIL,
        passwordHash=generate_password_hash("1234"),
        firstName="Bianka",
        lastName="Edouard",
        major="Computer Science",
        interests=["Flask", "UI design", "algorithms"],
        bio="Student interested in web development, Python, and building useful campus tools.",
        contactInfo="student@example.com",
    )
    alex = User(
        scsuEmail="alex.mitchell@owls.southernct.edu",
        passwordHash=generate_password_hash("1234"),
        firstName="Alex",
        lastName="Mitchell",
        major="Computer Science",
    )
    priya = User(
        scsuEmail="priya.nair@owls.southernct.edu",
        passwordHash=generate_password_hash("1234"),
        firstName="Priya",
        lastName="Nair",
        major="Biology",
    )
    marcus = User(
        scsuEmail="marcus.reed@owls.southernct.edu",
        passwordHash=generate_password_hash("1234"),
        firstName="Marcus",
        lastName="Reed",
        major="History",
    )
    lena = User(
        scsuEmail="lena.ortiz@owls.southernct.edu",
        passwordHash=generate_password_hash("1234"),
        firstName="Lena",
        lastName="Ortiz",
        major="Chemistry",
    )
    john = User(
        scsuEmail="john.smith@owls.southernct.edu",
        passwordHash=generate_password_hash("1234"),
        firstName="John",
        lastName="Smith",
        major="Mathematics",
    )
    sarah = User(
        scsuEmail="sarah.lee@owls.southernct.edu",
        passwordHash=generate_password_hash("1234"),
        firstName="Sarah",
        lastName="Lee",
        major="English",
    )
    group_chat = User(
        scsuEmail="group.chat@owls.southernct.edu",
        passwordHash=generate_password_hash("1234"),
        firstName="Group",
        lastName="Chat",
        major="Campus Community",
    )

    db.session.add_all(
        [current_user, alex, priya, marcus, lena, john, sarah, group_chat]
    )
    db.session.flush()

    study_groups = [
        StudyGroup(
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
            creator=alex,
        ),
        StudyGroup(
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
            creator=current_user,
        ),
        StudyGroup(
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
            creator=priya,
        ),
        StudyGroup(
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
            creator=marcus,
        ),
        StudyGroup(
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
            creator=lena,
        ),
    ]

    db.session.add_all(study_groups)
    db.session.flush()

    db.session.add_all(
        [
            GroupMembership(member=current_user, group=study_groups[0]),
            GroupMembership(member=alex, group=study_groups[0]),
            GroupMembership(member=priya, group=study_groups[0]),
            GroupMembership(member=current_user, group=study_groups[1]),
            GroupMembership(member=marcus, group=study_groups[1]),
            GroupMembership(member=priya, group=study_groups[2]),
            GroupMembership(member=lena, group=study_groups[2]),
            GroupMembership(member=marcus, group=study_groups[2]),
            GroupMembership(member=alex, group=study_groups[2]),
            GroupMembership(member=marcus, group=study_groups[3]),
            GroupMembership(member=current_user, group=study_groups[3]),
            GroupMembership(member=alex, group=study_groups[3]),
            GroupMembership(member=lena, group=study_groups[4]),
            GroupMembership(member=priya, group=study_groups[4]),
        ]
    )

    current_user.favoriteStudyGroups.extend([study_groups[0], study_groups[3]])

    db.session.add_all(
        [
            Message(
                sender=john,
                recipient=current_user,
                content="Hey, are we meeting today?",
            ),
            Message(
                sender=current_user,
                recipient=john,
                content="Yes, at 3 PM in the library.",
            ),
        ]
    )

    db.session.commit()
