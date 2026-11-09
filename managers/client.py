import httpx

from trapbook_self.http.dispatch import Dispatch
from trapbook_self.http.harvest import grab
from trapbook_self.managers.user import Users


class Client:
    def __init__(self, jar, *, timeout=30.0, proxy=None):
        self.jar = dict(jar)
        self._timeout = timeout
        self._proxy = proxy
        self._c = None
        self._d = None
        self.users = None
        self.me = None

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *a):
        await self.close()

    async def start(self):
        kw = {"timeout": self._timeout}
        if self._proxy:
            kw["proxy"] = self._proxy
        self._c = httpx.AsyncClient(**kw)
        t = await grab(self._c, self.jar)
        self._d = Dispatch(self._c, self.jar, t)
        self.users = Users(self._d)
        self.me = await self.users.me()
        return self

    async def close(self):
        if self._c:
            await self._c.aclose()
            self._c = None

    async def call(self, op, var):
        if not self._d:
            raise RuntimeError("not started")
        return await self._d.call(op, var)

    def __repr__(self):
        uid = self.me.id if self.me else "-"
        return f"<Client {uid}>"