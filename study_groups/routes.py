from flask import (
    Blueprint,
    abort,
    current_app,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from .view_models import study_group_detail_view_model, study_group_view_model


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


@study_groups_bp.get("/study-groups/<group_id>")
def detail(group_id: str) -> str:
    store = current_app.config["DATA_STORE"]
    current_user, group = _study_group_detail_data(
        store,
        session.get("user_id"),
        group_id,
    )
    if group is None:
        abort(404)

    return render_template(
        "study_groups/detail.html",
        group=study_group_detail_view_model(group, current_user),
        current_user=current_user,
    )


@study_groups_bp.post("/study-groups/<group_id>/join")
def join_group(group_id: str):
    store = current_app.config["DATA_STORE"]
    store.join_study_group(session.get("user_id"), group_id)
    if (request.form.get("next") or request.args.get("next")) == "detail":
        return redirect(url_for("study_groups.detail", group_id=group_id))

    return redirect(url_for("study_groups.listings"))


@study_groups_bp.post("/study-groups/<group_id>/leave")
def leave_group(group_id: str):
    store = current_app.config["DATA_STORE"]
    store.leave_study_group(session.get("user_id"), group_id)
    if (request.form.get("next") or request.args.get("next")) == "detail":
        return redirect(url_for("study_groups.detail", group_id=group_id))

    return redirect(url_for("study_groups.listings"))


@study_groups_bp.post("/study-groups/<group_id>/delete")
def delete_group(group_id: str):
    store = current_app.config["DATA_STORE"]
    store.delete_study_group(session.get("user_id"), group_id)
    return redirect(url_for("study_groups.listings"))


def _study_group_detail_data(store, user_id, group_id):
    detail_data = getattr(store, "study_group_detail_data", None)
    if detail_data is not None:
        return detail_data(user_id, group_id)

    current_user, groups = store.study_group_listing_data(user_id)
    group = next(
        (group for group in groups if str(group.id) == str(group_id)),
        None,
    )
    return current_user, group


def _is_active_member(group, user) -> bool:
    return any(
        membership.member is not None
        and membership.member.id == user.id
        and membership.status == "active"
        for membership in group.memberships
    )
