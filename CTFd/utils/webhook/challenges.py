import datetime

from CTFd.models import Challenges, Solves, Teams, Users
from CTFd.utils import get_config
from CTFd.utils.dates import tsformat
from CTFd.utils.modes import (
    generate_account_url,
    generate_team_url,
    generate_user_url,
    get_model,
)

USERS_MODE = "users"
TEAMS_MODE = "teams"


def get_all_solves(challenge_id):
    Model = get_model()

    mode = get_config("user_mode")
    freeze_time = get_config("freeze")

    if mode == TEAMS_MODE:

        solves = (
            Solves.query.add_columns(
                Model.name.label("account_name"),
                Solves.account_id,
                Solves.user_id,
                Solves.team_id,
                Users.name.label("user_name"),
                Teams.name.label("team_name"),
                Solves.date,
            )
            .join(Users, Solves.user_id == Users.id)
            .join(Teams, Solves.team_id == Teams.id)
            .filter(
                Solves.challenge_id == challenge_id,
                Model.banned == False,
                Model.hidden == False,
            )
            .order_by(Solves.date.asc())
        )

    elif mode == USERS_MODE:

        solves = (
            Solves.query.add_columns(
                Model.name.label("account_name"),
                Solves.account_id,
                Solves.user_id,
                Users.name.label("user_name"),
                Solves.date,
            )
            .join(Users, Solves.user_id == Users.id)
            .filter(
                Solves.challenge_id == challenge_id,
                Model.banned == False,
                Model.hidden == False,
            )
            .order_by(Solves.date.asc())
        )

    if freeze_time:
        dt = datetime.datetime.utcfromtimestamp(freeze_time)
        solves = solves.filter(Solves.date < dt)

    all_solves = []

    for solve in solves:
        one = {
            "account_type": "user" if mode == USERS_MODE else "team",
            "account": {
                "id": solve.account_id,
                "name": solve.account_name,
                "url": generate_account_url(account_id=solve.account_id),
            },
            "user": {
                "id": solve.user_id,
                "name": solve.user_name,
                "url": generate_user_url(user_id=solve.user_id),
            },
            "date": tsformat(solve.date),
        }
        if mode == TEAMS_MODE:
            one["team"] = {
                "id": solve.team_id,
                "name": solve.team_name,
                "url": generate_team_url(team_id=solve.team_id),
            }
        all_solves.append(one)

    return all_solves
