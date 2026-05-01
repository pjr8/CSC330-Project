from flask import Blueprint, render_template

from .mock_data import StudyGroupMockData
from .view_models import study_group_view_model


study_groups_bp = Blueprint("study_groups", __name__)
study_group_mock_data = StudyGroupMockData()


@study_groups_bp.route("/listings")
def listings() -> str:
    current_user, study_groups = study_group_mock_data.build()
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
