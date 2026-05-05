from flask import Blueprint, render_template, session

from db import db
from models import StudyGroup, User
from seed_data import DEMO_EMAIL

from .view_models import study_group_view_model


study_groups_bp = Blueprint("study_groups", __name__)


@study_groups_bp.route("/listings")
def listings() -> str:
    user_id = session.get("user_id")
    current_user = db.session.get(User, user_id) if user_id is not None else None
    if current_user is None:
        current_user = User.query.filter_by(scsuEmail=DEMO_EMAIL).first_or_404()
    study_groups = StudyGroup.query.order_by(StudyGroup.startAt.asc()).all()

    available_groups = [
        group
        for group in study_groups
        if group.status == "open" and group.hasAvailableSeat()
    ]
    favorite_groups = [
        group for group in current_user.favoriteStudyGroups if group.status == "open"
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
