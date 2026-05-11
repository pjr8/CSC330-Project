from datetime import datetime

from models import GroupMembership, StudyGroup, User


class StudyGroupMockData:
    """Creates model-backed study group mock data for the listings page."""

    def build(self) -> tuple[User, list[StudyGroup]]:
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

        self._add_members(study_groups[0], [current_user, alex, priya])
        self._add_members(study_groups[1], [current_user, marcus])
        self._add_members(study_groups[2], [priya, lena, marcus, alex])
        self._add_members(study_groups[3], [marcus, current_user, alex])
        self._add_members(study_groups[4], [lena, priya])

        self._favorite_group(current_user, study_groups[0])
        self._favorite_group(current_user, study_groups[3])

        return current_user, study_groups

    @staticmethod
    def _add_members(group: StudyGroup, users: list[User]) -> None:
        for user in users:
            GroupMembership(member=user, group=group)

    @staticmethod
    def _favorite_group(user: User, group: StudyGroup) -> None:
        if not StudyGroupMockData._contains_identity(user.favoriteStudyGroups, group):
            user.favoriteStudyGroups.append(group)
        if not StudyGroupMockData._contains_identity(group.favoritedBy, user):
            group.favoritedBy.append(user)

    @staticmethod
    def _contains_identity(items: list[object], target: object) -> bool:
        return any(item is target for item in items)
