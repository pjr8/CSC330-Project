from datetime import datetime

from models import StudyGroup, User


def study_group_view_model(
    group: StudyGroup, current_user: User
) -> dict[str, object]:
    active_member_count = sum(
        1 for membership in group.memberships if membership.status == "active"
    )
    is_member = _is_active_member(group, current_user)
    is_creator = _is_creator(group, current_user)
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
        "is_member": is_member,
        "is_creator": is_creator,
        "meeting_link": group.meetingLink,
        "has_available_seat": group.hasAvailableSeat(),
        "can_join": _is_open(group) and group.hasAvailableSeat() and not is_member,
        "can_leave": is_member and not is_creator,
        "can_delete": is_creator,
    }


def study_group_detail_view_model(
    group: StudyGroup, current_user: User
) -> dict[str, object]:
    view_model = study_group_view_model(group, current_user)
    is_full = not group.hasAvailableSeat()
    members = [
        {
            "name": _member_display_name(membership.member),
            "major": membership.member.major if membership.member else "",
            "role": _membership_role(group, membership.member, membership.role),
        }
        for membership in group.memberships
        if membership.status == "active" and membership.member is not None
    ]

    view_model.update(
        {
            "members": members,
            "is_open": _is_open(group),
            "is_full": is_full,
            "show_meeting_link": bool(group.meetingLink) and view_model["is_member"],
        }
    )
    view_model["join_state"] = _join_state(view_model)
    return view_model


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


def _is_open(group: StudyGroup) -> bool:
    return group.status.lower() == "open"


def _is_active_member(group: StudyGroup, target: User) -> bool:
    return any(
        membership.member is not None
        and membership.member.id == target.id
        and membership.status == "active"
        for membership in group.memberships
    )


def _is_creator(group: StudyGroup, target: User) -> bool:
    return group.creator is not None and group.creator.id == target.id


def _member_display_name(member: User | None) -> str:
    if member is None:
        return "Southern student"

    return member.getFullName() or member.firstName or member.scsuEmail


def _membership_role(group: StudyGroup, member: User | None, role: str) -> str:
    if (
        group.creator is not None
        and member is not None
        and member.id == group.creator.id
    ):
        return "Host"

    return role.title()


def _join_state(view_model: dict[str, object]) -> str:
    if view_model["is_member"]:
        return "joined"
    if view_model["can_join"]:
        return "join"
    if view_model["is_full"]:
        return "full"
    return "closed"
