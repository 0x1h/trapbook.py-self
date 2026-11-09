from trapbook_self.errors import SelfLaneBroken


class User:
    def __init__(self, raw):
        self.raw = raw
        self.id = raw.get("id", "")
        self.name = raw.get("name", "")
        self.url = raw.get("url") or raw.get("profile_url", "")
        self.pic = (raw.get("profile_picture") or {}).get("uri", "")
        self.cover = (raw.get("cover_photo") or {}).get("url", "")

    def __repr__(self):
        return f"<User {self.id} {self.name!r}>"


class Users:
    def __init__(self, d):
        self.d = d

    async def me(self):
        return User(await self.get("me"))

    async def get(self, uid):
        j = await self.d.call("UserQuery", {"userID": uid})
        u = (j.get("user") or j.get("data", {}).get("user") or j.get("me"))
        if not u:
            raise SelfLaneBroken("user", reason=uid)
        return u

    async def many(self, ids):
        out = []
        for i in ids:
            out.append(User(await self.get(i)))
        return out