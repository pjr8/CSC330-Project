from datetime import datetime

from models import StudyGroup, User


def study_group_view_model(
    group: StudyGroup, current_user: User
) -> dict[str, object]:
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
        "is_favorited": _contains_user(group.favoritedBy, current_user),
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


def _contains_user(items: list[User], target: User) -> bool:
    return any(user.id == target.id for user in items)
