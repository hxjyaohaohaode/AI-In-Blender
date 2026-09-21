"""Bounded verified HTTP used exclusively in the external worker process."""
import json
import ssl
import time
from urllib import request, error


class ProviderError(RuntimeError):
    pass


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ProviderError("Provider redirected the request; configure its final URL")


class HTTPClient:
    def __init__(self, config):
        self.config = config
        self.opener = request.build_opener(NoRedirect(), request.HTTPSHandler(
            context=ssl.create_default_context()))

    def call(self, url, payload=None, method=None, *, binary=False, data=None,
             content_type="application/json", authenticated=True, max_bytes=16_000_000):
        headers = {"Content-Type": content_type, "User-Agent": "AI-In-Blender/3.0"}
        if authenticated and self.config.api_key:
            headers["Authorization"] = "Bearer " + self.config.api_key
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = request.Request(url, data=data, headers=headers,
                              method=method or ("POST" if data is not None else "GET"))
        # POST requests are not retried automatically: a timeout may have accepted a billable job.
        for attempt in range(3 if req.method == "GET" else 1):
            try:
                with self.opener.open(req, timeout=min(self.config.timeout, 120)) as response:
                    raw = response.read(max_bytes + 1)
                if len(raw) > max_bytes:
                    raise ProviderError("Provider response exceeds the size limit")
                return raw if binary else json.loads(raw.decode("utf-8"))
            except error.HTTPError as exc:
                if req.method == "GET" and exc.code in {429, 502, 503, 504} and attempt < 2:
                    exc.close()
                    time.sleep(2 ** attempt)
                    continue
                exc.close()
                # Never echo upstream response bodies (they may contain submitted secrets).
                raise ProviderError(f"Provider returned HTTP {exc.code}; check endpoint, model, credentials and quota") from None
            except (error.URLError, TimeoutError, OSError) as exc:
                raise ProviderError(f"Provider connection failed ({type(exc).__name__})") from None
            except (json.JSONDecodeError, UnicodeDecodeError):
                raise ProviderError("Provider returned invalid JSON") from None
