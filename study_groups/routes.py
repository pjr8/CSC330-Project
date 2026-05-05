from flask import Blueprint, current_app, redirect, render_template, session, url_for

from .view_models import study_group_view_model


study_groups_bp = Blueprint("study_groups", __name__)


@study_groups_bp.route("/listings")
def listings() -> str:
    store = current_app.config["DATA_STORE"]
    current_user, study_groups = store.study_group_listing_data(session.get("user_id"))
    available_groups = [
        group
        for group in study_groups
        if group.status == "open"
        and (group.hasAvailableSeat() or _is_active_member(group, current_user))
    ]
    favorite_groups = [
        group
        for group in current_user.favoriteStudyGroups
        if group.status == "open"
    ]

    return render_template(
        "study_groups/listings.html",
        available_groups=[
            study_group_view_model(group, current_user)
            for group in available_groups
        ],
        favorite_groups=[
            study_group_view_model(group, current_user)
            for group in favorite_groups
        ],
        current_user=current_user,
    )


@study_groups_bp.post("/study-groups/<group_id>/join")
def join_group(group_id: str):
    store = current_app.config["DATA_STORE"]
    store.join_study_group(session.get("user_id"), group_id)
    return redirect(url_for("study_groups.listings"))


def _is_active_member(group, user) -> bool:
    return any(
        membership.member is not None
        and membership.member.id == user.id
        and membership.status == "active"
        for membership in group.memberships
    )
