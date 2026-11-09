import httpx

from trapbook_self.errors import SelfLaneBroken, SessionInvalidError
from trapbook_self.http.harvest import Tokens, grab

API = "https://www.facebook.com/api/graphql/"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0.0.0 Safari/537.36")


class Dispatch:
    def __init__(self, c, jar, t):
        self.c = c
        self.jar = jar
        self.t = t

    def need(self):
        return self.t.dead()

    async def fresh(self):
        self.t = await grab(self.c, self.jar)
        return self.t

    async def call(self, op, var):
        if op not in self.t.docs:
            raise SelfLaneBroken("op", reason=op)
        if self.need():
            await self.fresh()

        r = await self._post(op, var)

        if self._dead(r):
            await self.fresh()
            if op not in self.t.docs:
                raise SelfLaneBroken("op", reason=op)
            r = await self._post(op, var)

        if self._dead(r):
            raise SessionInvalidError("dead after refetch")

        if r.status_code >= 400:
            raise SelfLaneBroken("http", reason=f"{r.status_code} {op}")

        try:
            j = r.json()
        except ValueError as e:
            raise SelfLaneBroken("json", reason=f"{op} {str(e)[:40]}") from e

        if err := j.get("error"):
            raise SelfLaneBroken("gql", reason=f"{op} {err}")

        return j.get("data") or j

    def _dead(self, r):
        if r.status_code in (401, 403):
            return True
        u = str(r.url).lower()
        if any(b in u for b in ("/login/", "login.php", "checkpoint")):
            return True
        try:
            j = r.json()
        except ValueError:
            return False
        err = j.get("error") or {}
        return err.get("code") in (1357001, 1357004, 1357031)

    async def _post(self, op, var):
        return await self.c.post(
            API,
            data={
                "av": self.jar.get("c_user", "0"),
                "fb_dtsg": self.t.dtsg,
                "lsd": self.t.lsd,
                "jazoest": self.t.jz,
                "fb_api_req_friendly_name": op,
                "doc_id": self.t.docs[op],
                "variables": _dump(var),
                "server_timestamps": "true",
            },
            cookies=self.jar,
            headers={
                "User-Agent": UA,
                "X-FB-Friendly-Name": op,
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "https://www.facebook.com",
                "Referer": "https://www.facebook.com/",
            },
            timeout=httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0),
        )


def _dump(v):
    import json
    return json.dumps(v, separators=(",", ":"))