"""Reddit API client with OAuth and rate limiting."""

import time
import httpx
from typing import Optional
from tenacity import retry, stop_after_attempt, wait_exponential


REDDIT_API = "https://oauth.reddit.com"
REDDIT_RATE_LIMIT = 100  # QPM free tier


class RedditClient:
    """Reddit API client with OAuth + rate limiting."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        username: str,
        password: str,
        user_agent: str = "redex/0.1.0",
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.username = username
        self.password = password
        self.user_agent = user_agent

        self._access_token: Optional[str] = None
        self._token_expiry: float = 0
        self._request_timestamps: list[float] = []

        self._http = httpx.AsyncClient(timeout=30.0)

    @classmethod
    def from_config(cls, config: dict):
        return cls(
            client_id=config["client_id"],
            client_secret=config["client_secret"],
            username=config["username"],
            password=config["password"],
            user_agent=config.get("user_agent", "redex/0.1.0"),
        )

    # ---- Rate limiting ----

    def _throttle(self):
        """Enforce rate limit: max 100 requests/minute."""
        now = time.time()
        # Remove timestamps older than 60 seconds
        self._request_timestamps = [ts for ts in self._request_timestamps if now - ts < 60]
        if len(self._request_timestamps) >= REDDIT_RATE_LIMIT:
            wait = 60 - (now - self._request_timestamps[0]) + 1
            time.sleep(wait)
        self._request_timestamps.append(now)

    # ---- Auth ----

    async def authenticate(self) -> bool:
        """Authenticate via OAuth2 (password flow). Returns True on success."""
        self._throttle()
        resp = await self._http.post(
            f"{REDDIT_API}/access_token",
            data={
                "grant_type": "password",
                "username": self.username,
                "password": self.password,
            },
            auth=(self.client_id, self.client_secret),
            headers={"User-Agent": self.user_agent},
        )
        if resp.status_code == 200:
            data = resp.json()
            self._access_token = data["access_token"]
            # Reddit tokens typically last 1 hour
            self._token_expiry = time.time() + data.get("expires_in", 3600)
            return True
        return False

    async def _get_token(self) -> str:
        """Get valid access token, re-authenticating if needed."""
        if not self._access_token or time.time() >= self._token_expiry - 60:
            await self.authenticate()
        return self._access_token

    # ---- API Methods ----

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
    async def get_subreddit_posts(
        self, sub: str, limit: int = 100, after: str = None
    ) -> dict:
        """Fetch posts from a subreddit."""
        self._throttle()
        token = await self._get_token()
        params = {"limit": limit}
        if after:
            params["after"] = after

        resp = await self._http.get(
            f"{REDDIT_API}/r/{sub}/hot.json",
            params=params,
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": self.user_agent,
            },
        )
        resp.raise_for_status()
        return resp.json()["data"]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
    async def get_post_comments(self, post_id: str, depth: int = 10) -> dict:
        """Fetch comments for a post."""
        self._throttle()
        token = await self._get_token()

        resp = await self._http.get(
            f"{REDDIT_API}/api/info",
            params={"id": f"t3_{post_id}"},
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": self.user_agent,
            },
        )
        resp.raise_for_status()
        return resp.json()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
    async def get_comments_by_post(self, post_id: str, limit: int = 100) -> list[dict]:
        """Fetch comment tree for a post."""
        self._throttle()
        token = await self._get_token()

        resp = await self._http.get(
            f"{REDDIT_API}/r/na/comments/{post_id}.json",
            params={"limit": limit},
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": self.user_agent,
            },
        )
        resp.raise_for_status()
        return resp.json()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
    async def get_saved_posts(self, limit: int = 100) -> dict:
        """Fetch user's saved posts."""
        self._throttle()
        token = await self._get_token()

        resp = await self._http.get(
            f"{REDDIT_API}/user/{self.username}/saved.json",
            params={"limit": limit},
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": self.user_agent,
            },
        )
        resp.raise_for_status()
        return resp.json()["data"]

    async def close(self):
        await self._http.aclose()
