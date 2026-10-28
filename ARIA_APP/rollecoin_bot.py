"""Automatizacion web para RolleCoin usando solo stdlib (urllib)."""
import urllib.request
import urllib.parse
import http.cookiejar
import ssl
_CTX = ssl._create_unverified_context()


class RolleCoinBot:
    def __init__(self, base_url="https://rollecoin.com"):
        self.base = base_url.rstrip("/")
        self.cj = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=_CTX), urllib.request.HTTPCookieProcessor(self.cj))

    def fetch(self, path="/", params=None):
        url = self.base + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        try:
            with self.opener.open(url, timeout=15) as r:
                return {"status": "ok", "code": r.status, "body": r.read().decode("utf-8", "replace")[:2000]}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    def post(self, path="/", data=None):
        url = self.base + path
        payload = urllib.parse.urlencode(data or {}).encode()
        req = urllib.request.Request(url, data=payload, method="POST")
        try:
            with self.opener.open(req, timeout=15) as r:
                return {"status": "ok", "code": r.status, "body": r.read().decode("utf-8", "replace")[:2000]}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}


def run(action="fetch", path="/", data=None):
    bot = RolleCoinBot()
    if action == "post":
        return bot.post(path, data)
    return bot.fetch(path)