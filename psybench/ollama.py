"""Small Ollama HTTP adapter; never contacts a model registry in offline mode."""

import base64
import json
import re
import urllib.error
import urllib.parse
import urllib.request


def metadata_identity(metadata):
    """ollama-metadata-identity-v1: ignore only local presentation details.

    Preserve unknown fields, template/system text, blob hashes and the order of
    repeated values (notably stop tokens). Never mutate the saved metadata.
    """
    result = dict(metadata)
    result.pop("modified_at", None)
    if isinstance(result.get("modelfile"), str):
        # Generated blob directives precede TEMPLATE. Do not rewrite prompt text.
        header, separator, template = result["modelfile"].partition("TEMPLATE ")
        header = re.sub(r"(?m)^FROM /[^\n]+/(sha256-[0-9a-f]{64})$", r"FROM \1", header)
        result["modelfile"] = header + separator + template
    if isinstance(result.get("parameters"), str):
        groups = {}
        for line in result["parameters"].splitlines():
            parts = line.split(maxsplit=1)
            if len(parts) != 2:
                # Unexpected output remains subject to exact comparison.
                break
            groups.setdefault(parts[0], []).append(parts[1])
        else:
            result["parameters"] = groups
    return result


class Ollama:
    def __init__(self, url, timeout=600):
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("Ollama URL must be an HTTP loopback address")
        self.url = url.rstrip("/")
        self.timeout = timeout
        # Do not send local inference through HTTP_PROXY / HTTPS_PROXY.
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def request(self, path, payload=None):
        body = None if payload is None else json.dumps(payload).encode()
        request = urllib.request.Request(
            self.url + path, data=body, headers={"Content-Type": "application/json"}
        )
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                return json.load(response)
        except (urllib.error.URLError, TimeoutError) as exc:
            raise RuntimeError(f"Ollama {path}: {exc}") from exc

    def version(self):
        return self.request("/api/version")["version"]

    def models(self):
        return {m["name"]: m for m in self.request("/api/tags")["models"]}

    def pull(self, name):
        self.request("/api/pull", {"model": name, "stream": False})

    def show(self, name):
        return self.request("/api/show", {"model": name})

    def generate(self, name, prompt, images, options, structured=False, think=None):
        payload = {
            "model": name,
            "prompt": prompt,
            "stream": False,
            "keep_alive": "5m",
            "options": options,
        }
        if images:
            payload["images"] = [base64.b64encode(image).decode() for image in images]
        if structured:
            payload["format"] = "json"
        if think is not None:
            payload["think"] = think
        return self.request("/api/generate", payload)

    def unload(self, name):
        self.request("/api/generate", {"model": name, "keep_alive": 0, "stream": False})
