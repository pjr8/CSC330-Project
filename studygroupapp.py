from datetime import datetime

from flask import Flask, render_template

from models import GroupMembership, StudyGroup, User


def create_app() -> Flask:
    app = Flask(__name__)

    @app.route("/")
    def index() -> str:
        return "Study Group App"

    @app.route("/listings")
    def listings() -> str:
        current_user, study_groups = _build_mock_study_group_data()
        available_groups = [
            group
            for group in study_groups
            if group.status == "open" and group.hasAvailableSeat()
        ]
        favorite_groups = [
            group
            for group in current_user.favoriteStudyGroups
            if group.status == "open"
        ]

        return render_template(
            "listings.html",
            available_groups=[
                _study_group_view_model(group, current_user)
                for group in available_groups
            ],
            favorite_groups=[
                _study_group_view_model(group, current_user)
                for group in favorite_groups
            ],
            current_user=current_user,
        )

    return app


def _build_mock_study_group_data() -> tuple[User, list[StudyGroup]]:
    """Create model-backed mock listings until persistent storage is connected."""
    current_user = User(
        scsuEmail="avery.santos@owls.southernct.edu",
        firstName="Avery",
        lastName="Santos",
        major="Computer Science",
        interests=["Software design", "Mathematics", "Research writing"],
    )
    alex = User(
        scsuEmail="alex.mitchell@owls.southernct.edu",
        firstName="Alex",
        lastName="Mitchell",
        major="Computer Science",
    )
    priya = User(
        scsuEmail="priya.nair@owls.southernct.edu",
        firstName="Priya",
        lastName="Nair",
        major="Biology",
    )
    marcus = User(
        scsuEmail="marcus.reed@owls.southernct.edu",
        firstName="Marcus",
        lastName="Reed",
        major="History",
    )
    lena = User(
        scsuEmail="lena.ortiz@owls.southernct.edu",
        firstName="Lena",
        lastName="Ortiz",
        major="Chemistry",
    )

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

    _add_members(study_groups[0], [current_user, alex, priya])
    _add_members(study_groups[1], [current_user, marcus])
    _add_members(study_groups[2], [priya, lena, marcus, alex])
    _add_members(study_groups[3], [marcus, current_user, alex])
    _add_members(study_groups[4], [lena, priya])

    _favorite_group(current_user, study_groups[0])
    _favorite_group(current_user, study_groups[3])

    return current_user, study_groups


def _add_members(group: StudyGroup, users: list[User]) -> None:
    for user in users:
        GroupMembership(member=user, group=group)


def _favorite_group(user: User, group: StudyGroup) -> None:
    if not _contains_identity(user.favoriteStudyGroups, group):
        user.favoriteStudyGroups.append(group)
    if not _contains_identity(group.favoritedBy, user):
        group.favoritedBy.append(user)


def _study_group_view_model(group: StudyGroup, current_user: User) -> dict[str, object]:
    active_member_count = sum(
        1 for membership in group.memberships if membership.status == "active"
    )
    is_virtual = group.modality.lower() == "virtual"
    is_hybrid = group.modality.lower() == "hybrid"
    location = group.location

    if is_virtual:
        location = "Virtual meeting"
    elif is_hybrid:
        location = f"{group.location} + virtual option"

    if group.maxMembers > 0:
        capacity = f"{active_member_count} / {group.maxMembers} members"
    else:
        capacity = f"{active_member_count} members, open capacity"

    return {
        "id": group.id,
        "title": group.title,
        "subject": group.subject,
        "description": group.description,
        "meeting_time": _format_meeting_time(group),
        "location": location,
        "modality": group.modality,
        "capacity": capacity,
        "active_member_count": active_member_count,
        "max_members": group.maxMembers,
        "status": group.status.title(),
        "creator_name": group.creator.getFullName() if group.creator else "Student host",
        "is_favorited": _contains_identity(group.favoritedBy, current_user),
        "meeting_link": group.meetingLink,
        "has_available_seat": group.hasAvailableSeat(),
    }


def _format_meeting_time(group: StudyGroup) -> str:
    if group.startAt is None:
        return "Meeting time to be announced"

    start = _format_meeting_start(group.startAt)
    if group.endAt is None:
        return start

    end = _format_clock_time(group.endAt)
    return f"{start} to {end}"


def _format_meeting_start(start_at: datetime) -> str:
    weekday_month = start_at.strftime("%A, %B")
    return f"{weekday_month} {start_at.day} at {_format_clock_time(start_at)}"


def _format_clock_time(value: datetime) -> str:
    return value.strftime("%I:%M %p").lstrip("0")


def _contains_identity(items: list[object], target: object) -> bool:
    return any(item is target for item in items)


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
