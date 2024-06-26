import os
import time

from flask import current_app as app

from CTFd.constants.themes import DEFAULT_THEME
from CTFd.utils import get_app_config, get_config
from CTFd.utils.modes import TEAMS_MODE, USERS_MODE


def ctf_name():
    name = get_config("ctf_name")
    return name if name else "CTFd"


def user_mode():
    return get_config("user_mode")


def is_users_mode():
    return user_mode() == USERS_MODE


def is_teams_mode():
    return user_mode() == TEAMS_MODE


def ctf_logo():
    return get_config("ctf_logo")


def ctf_theme():
    theme = get_config("ctf_theme")
    return theme if theme else ""


def ctf_theme_candidates():
    yield ctf_theme()
    if bool(get_app_config("THEME_FALLBACK")):
        yield DEFAULT_THEME


def is_setup():
    return bool(get_config("setup")) is True


def is_scoreboard_frozen():
    freeze = get_config("freeze")

    if freeze:
        freeze = int(freeze)
        if freeze < time.time():
            return True

    return False


def get_webhook_config():
    uri = get_config("webhook_uri", None)
    if uri is None or uri == "None" or uri == "":
        uri = None
    elif not uri.startswith("http://") and not uri.startswith("https://"):
        uri = "http://" + uri

    secret = str(get_config("webhook_secret", "secret_ctfd_webhook")).encode("utf-8")
    algorithm = get_config("webhook_algorithm", "hmac_sha1")
    return uri, secret, algorithm


def get_bonus_score_rate():
    conf_string = get_config("bonus_score_rate", "0.05, 0.03, 0.01")
    conf_array = conf_string.split(",")
    rates = []
    try:
        for r in conf_array:
            r = r.strip()
            if r.endswith("%"):
                rates.append(float(r[:-1]) / 100)
            else:
                rates.append(float(r))
    except ValueError:
        rates = [0]
    if len(rates) < 1:
        rates = [0]
    return rates


def can_send_mail():
    return mailserver() or mailgun()


def get_mail_provider():
    mail_provider = app.config.get("MAIL_PROVIDER")
    if mail_provider:
        return mail_provider
    if get_config("mail_server") and get_config("mail_port"):
        return "smtp"
    if get_config("mailgun_api_key") and get_config("mailgun_base_url"):
        return "mailgun"
    if app.config.get("MAIL_SERVER") and app.config.get("MAIL_PORT"):
        return "smtp"
    if app.config.get("MAILGUN_API_KEY") and app.config.get("MAILGUN_BASE_URL"):
        return "mailgun"


def mailgun():
    if app.config.get("MAILGUN_API_KEY") and app.config.get("MAILGUN_BASE_URL"):
        return True
    if get_config("mailgun_api_key") and get_config("mailgun_base_url"):
        return True
    return False


def mailserver():
    if app.config.get("MAIL_SERVER") and app.config.get("MAIL_PORT"):
        return True
    if get_config("mail_server") and get_config("mail_port"):
        return True
    return False


def get_themes():
    dir = os.path.join(app.root_path, "themes")
    return [
        name
        for name in os.listdir(dir)
        if os.path.isdir(os.path.join(dir, name)) and name != "admin"
    ]
