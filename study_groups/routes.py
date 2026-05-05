from flask import Blueprint, current_app, render_template, session

from .view_models import study_group_view_model


study_groups_bp = Blueprint("study_groups", __name__)


@study_groups_bp.route("/listings")
def listings() -> str:
    store = current_app.config["DATA_STORE"]
    current_user, study_groups = store.study_group_listing_data(session.get("user_id"))
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
