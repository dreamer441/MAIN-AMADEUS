import json
import urllib.error
import urllib.request
from typing import Any


DEFAULT_OLLAMA_HOST = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "qwen3:32b"


class OllamaClientError(RuntimeError):
    """Raised when AMADEUS cannot get a valid response from Ollama."""


class OllamaClient:
    """Small client for Ollama's local HTTP API."""

    def __init__(
        self,
        model: str = DEFAULT_OLLAMA_MODEL,
        host: str = DEFAULT_OLLAMA_HOST,
        timeout_seconds: int = 600,
    ) -> None:
        # Keep Ollama settings centralized so future model selection is easy to add.
        self.model = model
        self.host = host.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        """Send a prompt to Ollama and return the generated response text."""
        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "num_ctx": 8192,
            },
        }
        if system_prompt:
            payload["system"] = system_prompt

        data = self._post_json("/api/generate", payload)
        response = data.get("response")
        if not isinstance(response, str):
            raise OllamaClientError("Ollama returned a response AMADEUS could not read.")

        clean_response = response.strip()
        if not clean_response:
            raise OllamaClientError("Ollama returned an empty response.")

        return clean_response

    def health_check(self) -> dict[str, object]:
        """Return basic Ollama availability and model status information."""
        data = self._get_json("/api/tags")
        models = data.get("models", [])
        model_names = self._extract_model_names(models)

        return {
            "ok": True,
            "host": self.host,
            "model": self.model,
            "model_available": self.model in model_names,
            "available_models": model_names,
        }

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        """POST JSON to Ollama and return parsed JSON."""
        request = urllib.request.Request(
            url=f"{self.host}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        return self._open_json_request(request)

    def _get_json(self, path: str) -> dict[str, Any]:
        """GET JSON from Ollama and return parsed JSON."""
        request = urllib.request.Request(url=f"{self.host}{path}", method="GET")
        return self._open_json_request(request)

    def _open_json_request(self, request: urllib.request.Request) -> dict[str, Any]:
        """Open an Ollama HTTP request and parse the JSON body."""
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw_body = response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            message = self._read_http_error(error)
            raise OllamaClientError(message) from error
        except urllib.error.URLError as error:
            raise OllamaClientError(
                "Could not connect to Ollama. Start Ollama and make sure it is running "
                f"at {self.host}."
            ) from error
        except TimeoutError as error:
            raise OllamaClientError("Ollama took too long to respond.") from error

        try:
            parsed = json.loads(raw_body)
        except json.JSONDecodeError as error:
            raise OllamaClientError("Ollama returned invalid JSON.") from error

        if not isinstance(parsed, dict):
            raise OllamaClientError("Ollama returned an unexpected response shape.")

        return parsed

    def _read_http_error(self, error: urllib.error.HTTPError) -> str:
        """Convert an Ollama HTTP error into a user-readable message."""
        body = error.read().decode("utf-8", errors="replace")
        lower_body = body.lower()

        # Missing-model errors should tell the user the exact setup command.
        if "model" in lower_body and ("not found" in lower_body or "pull" in lower_body):
            return (
                f"Ollama model '{self.model}' is not available. Run `ollama pull "
                f"{self.model}` and try again."
            )

        if body.strip():
            return f"Ollama returned HTTP {error.code}: {body.strip()}"

        return f"Ollama returned HTTP {error.code}."

    def _extract_model_names(self, models: object) -> list[str]:
        """Extract model names from Ollama's /api/tags response."""
        if not isinstance(models, list):
            return []

        names: list[str] = []
        for model in models:
            if not isinstance(model, dict):
                continue

            name = model.get("name") or model.get("model")
            if isinstance(name, str):
                names.append(name)

        return sorted(names)
