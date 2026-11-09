import re
import time
from dataclasses import dataclass, field

import httpx

from trapbook_self.errors import SelfLaneBroken, SessionInvalidError

URL = "https://www.facebook.com/"
BAD = ("/login/", "login.php", "checkpoint", "/recover/")

DTSG = (
    re.compile(r'"DTSGInitialData",\[\],\{"token":"([^"]+)"'),
    re.compile(r'"dtsg":\{"token":"([^"]+)"'),
    re.compile(r'name="fb_dtsg" value="([^"]+)"'),
)
LSD = (
    re.compile(r'"LSD",\[\],\{"token":"([^"]+)"'),
    re.compile(r'name="lsd" value="([^"]+)"'),
)
JZ = (
    re.compile(r'name="jazoest" value="(\d+)"'),
    re.compile(r'"jazoest":"(\d+)"'),
)
DOC = re.compile(r'"([A-Za-z][A-Za-z0-9_]{2,60})":\s*"?(\d{6,})"?')
ESC = (("\\/", "/"), ("\\u0025", "%"), ("\\u003C", "<"), ("\\u003E", ">"))


@dataclass(frozen=True)
class Tokens:
    dtsg: str
    lsd: str
    jz: str
    docs: dict[str, str] = field(default_factory=dict)
    at: float = 0.0
    ttl: int = 3600

    def dead(self, now=None):
        return ((now if now is not None else time.monotonic()) - self.at) > self.ttl

    def __repr__(self):
        return f"Tokens(docs={len(self.docs)}, age={time.monotonic() - self.at:.0f}s)"


def _clean(s):
    for a, b in ESC:
        s = s.replace(a, b)
    return s


def _hit(pats, s):
    for p in pats:
        m = p.search(s)
        if m:
            return m.group(1)
    return None


def _docs(s):
    out = {}
    for m in DOC.finditer(s):
        n, d = m.group(1), m.group(2)
        if 14 <= len(d) <= 22 and n not in out:
            out[n] = d
    return out


def _ok(r):
    u = str(r.url).lower()
    if any(b in u for b in BAD):
        raise SessionInvalidError(f"dead: {u.split('?')[0]}")
    if r.status_code in (401, 403):
        raise SessionInvalidError(f"dead: {r.status_code}")


async def grab(c, jar):
    try:
        r = await c.get(
            URL,
            cookies=jar,
            follow_redirects=True,
            timeout=httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0),
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/126.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
    except httpx.HTTPError as e:
        raise SelfLaneBroken("fetch fail", reason=str(e)) from e

    _ok(r)
    h = _clean(r.text)

    dtsg = _hit(DTSG, h)
    lsd = _hit(LSD, h)
    jz = _hit(JZ, h)
    docs = _docs(h)

    miss = [k for k, v in (("dtsg", dtsg), ("lsd", lsd), ("jz", jz)) if not v]
    if miss:
        raise SelfLaneBroken("shape", reason=f"miss: {','.join(miss)}")
    if not docs:
        raise SelfLaneBroken("shape", reason="no docs")

    return Tokens(dtsg=dtsg, lsd=lsd, jz=jz, docs=docs, at=time.monotonic())


async def raw(c, jar):
    r = await c.get(URL, cookies=jar, follow_redirects=True)
    _ok(r)
    return _clean(r.text)