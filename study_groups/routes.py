from datetime import datetime

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
DEFAULT_LISTING_SORT = "soonest"
LISTING_SORT_OPTIONS = (
    ("soonest", "Soonest meeting"),
    ("title", "Title A-Z"),
    ("subject", "Subject A-Z"),
    ("seats", "Most seats"),
)


@study_groups_bp.route("/listings")
def listings() -> str:
    store = current_app.config["DATA_STORE"]
    current_user, study_groups = store.study_group_listing_data(session.get("user_id"))
    search_query = request.args.get("q", "").strip()
    sort_key = _listing_sort_key(request.args.get("sort", DEFAULT_LISTING_SORT))
    available_groups = [
        group
        for group in study_groups
        if group.status == "open"
        and (group.hasAvailableSeat() or _is_active_member(group, current_user))
    ]
    filtered_groups = _sort_study_groups(
        _search_study_groups(available_groups, search_query),
        sort_key,
    )
    favorite_groups = [
        group
        for group in current_user.favoriteStudyGroups
        if group.status == "open"
    ]

    return render_template(
        "study_groups/listings.html",
        available_groups=[
            study_group_view_model(group, current_user)
            for group in filtered_groups
        ],
        favorite_groups=[
            study_group_view_model(group, current_user)
            for group in favorite_groups
        ],
        current_user=current_user,
        search_query=search_query,
        sort_key=sort_key,
        sort_options=[
            {"value": value, "label": label}
            for value, label in LISTING_SORT_OPTIONS
        ],
        total_available_count=len(available_groups),
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


def _listing_sort_key(value: str | None) -> str:
    allowed_values = {sort_value for sort_value, _ in LISTING_SORT_OPTIONS}
    if value in allowed_values:
        return value

    return DEFAULT_LISTING_SORT


def _search_study_groups(groups, search_query: str):
    normalized_query = search_query.casefold()
    if not normalized_query:
        return list(groups)

    terms = normalized_query.split()
    return [
        group
        for group in groups
        if all(term in _study_group_search_text(group) for term in terms)
    ]


def _study_group_search_text(group) -> str:
    creator_name = group.creator.getFullName() if group.creator else ""
    return " ".join(
        (
            group.title,
            group.subject,
            group.description,
            group.location,
            group.modality,
            creator_name,
        )
    ).casefold()


def _sort_study_groups(groups, sort_key: str):
    sortable_groups = list(groups)

    if sort_key == "title":
        return sorted(sortable_groups, key=lambda group: _text_sort_key(group.title))

    if sort_key == "subject":
        return sorted(
            sortable_groups,
            key=lambda group: (
                _text_sort_key(group.subject),
                _text_sort_key(group.title),
            ),
        )

    if sort_key == "seats":
        return sorted(
            sortable_groups,
            key=lambda group: (
                -_available_seat_count(group),
                _text_sort_key(group.title),
            ),
        )

    return sorted(
        sortable_groups,
        key=lambda group: (
            group.startAt is None,
            group.startAt or datetime.max,
            _text_sort_key(group.title),
        ),
    )


def _text_sort_key(value: str) -> str:
    return value.casefold()


def _available_seat_count(group) -> int:
    if group.maxMembers <= 0:
        return 1_000_000

    active_members = sum(
        1 for membership in group.memberships if membership.status == "active"
    )
    return max(group.maxMembers - active_members, 0)
