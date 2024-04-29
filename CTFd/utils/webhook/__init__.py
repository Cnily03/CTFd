import datetime
import hashlib
import hmac
import json
import threading
import uuid

import requests

from CTFd.models import Challenges
from CTFd.utils import get_config
from CTFd.utils.config import get_webhook_config
from CTFd.utils.modes import get_model
from CTFd.utils.webhook.challenges import get_all_solves


def calc_sig(content: bytes, key: bytes, algorithm: str):
    if algorithm == "hex":
        return key.hex()
    elif algorithm == "hmac_md5":
        return hmac.new(key, content, hashlib.md5).hexdigest()
    elif algorithm == "hmac_sha1":
        return hmac.new(key, content, hashlib.sha1).hexdigest()
    elif algorithm == "hmac_sha256":
        return hmac.new(key, content, hashlib.sha256).hexdigest()
    elif algorithm == "hmac_sha384":
        return hmac.new(key, content, hashlib.sha384).hexdigest()
    elif algorithm == "hmac_sha512":
        return hmac.new(key, content, hashlib.sha512).hexdigest()


class Webhook:
    @staticmethod
    def _post(uri, data_bytes, headers):
        requests.post(uri, data=data_bytes, headers=headers)

    @staticmethod
    def _post_async(uri, data, headers):
        thread = threading.Thread(target=Webhook._post, args=(uri, data, headers))
        thread.daemon = True
        thread.start()

    @staticmethod
    def send(data):
        if data is None:
            return

        uri, secret, algorithm = get_webhook_config()
        if uri is None:
            return
        json_bytes = json.dumps(data).encode("utf-8")
        signature = calc_sig(json_bytes, secret, algorithm)
        hookid = str(
            uuid.uuid3(uuid.NAMESPACE_URL, str(datetime.datetime.now().timestamp()))
        )
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "CTFd-Hookshot/1.0",
            "X-CTFd-Hook-ID": hookid,
            "X-CTFd-Hook-Sig": signature,
        }
        try:
            Webhook._post_async(uri, data=json_bytes, headers=headers)
        except Exception as e:
            print("Error sending webhook:", e)


USERS_MODE = "users"
TEAMS_MODE = "teams"


class Event:
    @staticmethod
    def solve(challenge_id, account_id):
        Model = get_model()

        freeze = True if get_config("freeze") else False
        challenge = Challenges.query.filter_by(id=challenge_id).first()
        solves = get_all_solves(challenge_id)
        mode = get_config("user_mode")
        solve_info = None
        for s in solves:
            if s["account"]["id"] == account_id:
                solve_info = s
                break
        if solve_info is None:
            # account is banned or hidden
            return None
        else:
            solves = list(filter(lambda x: x["date"] <= solve_info["date"], solves))
        data = {
            "event": "solve",
            "mode": mode,
            "freeze": freeze,
            "challenge_info": {
                "id": challenge_id,
                "name": challenge.name,
                "category": challenge.category,
                "solve_count": len(solves),
            },
            "solve_info": solve_info,
            "solves": solves,
        }
        return data
