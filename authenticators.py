import logging
from dataclasses import dataclass
import requests


logger = logging.getLogger(__name__)


class TokenNotFound(Exception):
    pass


@dataclass
class TokenInfo:
    user: str
    is_admin: bool
    is_approved: bool
    scopes: str


class StaticAuthenticator:

    def __init__(self, items):
        self.items = items

    def get_token_info(self, token: str) -> TokenInfo:
        try:
            info = self.items[token]
        except KeyError:
            raise TokenNotFound()

        user_id = info["id"]
        
        return TokenInfo(
            user=user_id,
            is_admin=info.get("is_admin", False),
            is_approved=info.get("is_approved", False),
            scopes=info.get("scopes", ""),
        )


class SageAuthenticator: # pragma: no cover - this should be covered as part of an integration test instead.

    def __init__(self, url, password):
        self.url = url
        self.password = password

    def get_token_info(self, token: str) -> TokenInfo:
        logger.info("getting token info")

        with requests.Session() as session:
            session.headers = {"Authorization": f"Sage {self.password}"}

            # fetch token info from auth site
            logger.info("requesting token info")
            r = session.post(self.url, timeout=5, json={"token": token})
            if r.status_code == 404:
                raise TokenNotFound()
            r.raise_for_status()

            token_info = r.json()

            # treat tokens not marked active as nonexistant
            if not "active" in token_info:
                raise TokenNotFound()

            username = token_info["username"]

            # fetch user info from auth site
            # TODO(sean) make this url part of config
            logger.info("requesting user info")
            r = session.get(f"https://auth.sagecontinuum.org/users/{username}", timeout=5)
            if r.status_code == 404:
                raise TokenNotFound()
            r.raise_for_status()

            user_info = r.json()

        return TokenInfo(
            user=username,
            is_admin=False,
            # TODO(sean) at the moment, setting is_admin = true makes the portal nearly unusable due to the
            # high number of requests. (admin users see *all* apps and repos on the portal by default!)
            # is_admin=user_info.get("is_superuser", False),
            is_approved=user_info.get("is_approved", False),
            scopes=token_info.get("scopes", ""),
        )
