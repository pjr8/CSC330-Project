# SCSU Study Group Scheduler

A Flask web app for Southern Connecticut State University students to create,
discover, join, and coordinate study groups. The app includes student account
signup/login, SQLite-backed study group persistence, profile management, and
member-only study group chats.

## Features

- SCSU-only account signup and login using `@southernct.edu` email addresses
- Home dashboard with navigation into the main student workflows
- Study group creation with date, time, modality, location/link, and capacity validation
- Study group listings with joined/favorite state and available-seat filtering
- Study group detail pages with roster, host information, and join/leave/delete actions
- Student profile viewing and editing
- Persistent group chats for each joined study group
- Seeded SQLite data for local development and tests

## Tech Stack

- Python 3.10+
- Flask 3
- SQLite
- Jinja templates
- CSS
- `unittest`

## Project Structure

```text
.
|-- accounts/              # Signup routes and account-store helpers
|-- messages/              # Study group chat routes
|-- study_groups/          # Study group listing/detail routes and view models
|-- static/                # CSS and image assets
|-- templates/             # Jinja HTML templates
|-- tests/                 # Unit and route tests
|-- app_store.py           # SQLite persistence layer and seed data
|-- models.py              # Dataclass domain models
|-- studygroupapp.py       # Flask app factory and main routes
`-- requirements.txt       # Python dependencies
```

## Getting Started

Create and activate a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the app:

```bash
python studygroupapp.py
```

Then open:

```text
http://127.0.0.1:5000
```

The SQLite database is created automatically at `instance/studygroups.sqlite3`
when the app starts. To reset local seed data, stop the server and delete that
database file.

## Seeded Login

Local development starts with a seeded test account:

```text
Email: test@southernct.edu
Password: 1234
```

You can also create a new account from the signup page using any
`@southernct.edu` email address.

## Main Routes

| Route | Purpose |
| --- | --- |
| `/` | Login page |
| `/signup` | Create an account |
| `/home` | Authenticated home dashboard |
| `/listings` | Browse available study groups |
| `/study-groups/<group_id>` | View study group details |
| `/create` | Create a study group |
| `/messages` | View/search chats for joined study groups |
| `/profile` | View the current user's profile |
| `/update-profile` | Edit the current user's profile |
| `/logout` | End the current session |

Most routes require an authenticated session. Unauthenticated users are
redirected to the login page.

## Running Tests

Run the full test suite with:

```bash
python -m unittest discover -s tests -p "test_*.py"
```

The tests use temporary SQLite databases where needed, so they do not modify
your local development database.

## Notes for Development

- `create_app()` in `studygroupapp.py` is the app factory used by both the
  development server and tests.
- `SQLiteStudyGroupStore` in `app_store.py` owns schema creation, persistence,
  seeded users, seeded study groups, memberships, favorites, and study group chats.
- Signup and login enforce Southern email addresses ending in `@southernct.edu`.
- Study group creators are automatically added as host members when a group is
  created.
