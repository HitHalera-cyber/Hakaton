"""A small client of Ollama (https://ollama.com), the local model server.

Only the standard library: the exe gets no new dependencies, and without
Ollama nothing changes. Models that see pictures are preferred — the sheet
is sent as an image along with what the program recognised.
"""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request

DEFAULT_URL = "http://localhost:11434"
# names of models that take images, best first
VISION = ("qwen2.5vl", "qwen3-vl", "gemma3", "llama3.2-vision", "minicpm-v", "llava",
          "granite3.2-vision", "mistral-small3", "moondream", "bakllava")
SUGGESTED = "qwen2.5vl:7b"  # what to «ollama pull» (gemma3:4b on a weak computer)


class OllamaError(RuntimeError):
    pass


def _open(req, timeout):
    # no proxy for the local server (a system proxy would swallow «localhost»)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        return opener.open(req, timeout=timeout)
    except urllib.error.URLError as exc:
        raise OllamaError(
            "Ollama не отвечает. Запустите её (значок Ollama в трее или команда «ollama serve») "
            f"и проверьте адрес ({exc.reason})") from exc


def models(url: str = DEFAULT_URL, timeout: float = 5.0) -> list[str]:
    """The models installed in Ollama."""
    with _open(urllib.request.Request(url.rstrip("/") + "/api/tags"), timeout) as r:
        data = json.loads(r.read().decode("utf-8"))
    return [m["name"] for m in data.get("models", [])]


def sees_images(name: str) -> bool:
    return any(v in name.lower() for v in VISION)


def pick_model(names: list[str]) -> str | None:
    """The best installed model: one that sees images, in the order of VISION."""
    for v in VISION:
        for n in names:
            if v in n.lower():
                return n
    return names[0] if names else None


def chat(messages: list[dict], model: str, url: str = DEFAULT_URL, images: list[bytes] = (),
         json_mode: bool = False, timeout: float = 900.0) -> str:
    """One answer of the model. ``images`` (PNG bytes) go with the last message."""
    msgs = [dict(m) for m in messages]
    if images and msgs:
        msgs[-1]["images"] = [base64.b64encode(b).decode("ascii") for b in images]
    body = {"model": model, "messages": msgs, "stream": False,
            "options": {"temperature": 0.1}}
    if json_mode:
        body["format"] = "json"
    req = urllib.request.Request(url.rstrip("/") + "/api/chat",
                                 data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with _open(req, timeout) as r:
        data = json.loads(r.read().decode("utf-8"))
    if "error" in data:
        raise OllamaError(f"Ollama: {data['error']}")
    return data.get("message", {}).get("content", "")
