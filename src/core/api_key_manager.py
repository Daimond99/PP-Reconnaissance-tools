"""
API Key Manager — handles AI Mode provider credentials the way Claude Code
does: check for a saved key, prompt if missing, validate before saving, and
never write the key to disk or logs in plain text.

Storage backends:
  - "saved"   -> OS credential store via the `keyring` package (encrypted,
                 survives restarts).
  - "session" -> kept only in an in-memory dict, wiped when the app closes.

The API key value itself must never be passed to any logging function.
"""

from __future__ import annotations

import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from src.config import AI_MODE_PROVIDERS, KEYRING_SERVICE_NAME

try:
    import keyring
    _KEYRING_AVAILABLE = True
except ImportError:
    _KEYRING_AVAILABLE = False


@dataclass
class ValidationResult:
    ok: bool
    message: str


class APIKeyManager:
    """Manages API keys for AI Mode providers ('openai', 'anthropic')."""

    def __init__(self):
        # session-only keys, never touch disk: {provider: key}
        self._session_keys: Dict[str, str] = {}

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def has_key(self, provider: str) -> bool:
        return self.get_key(provider) is not None

    def get_key(self, provider: str) -> Optional[str]:
        """Session key takes precedence, then the OS keyring."""
        if provider in self._session_keys:
            return self._session_keys[provider]
        if _KEYRING_AVAILABLE:
            try:
                cfg = AI_MODE_PROVIDERS[provider]
                return keyring.get_password(KEYRING_SERVICE_NAME, cfg["keyring_key"])
            except Exception:
                return None
        return None

    def is_saved_on_disk(self, provider: str) -> bool:
        if not _KEYRING_AVAILABLE:
            return False
        try:
            cfg = AI_MODE_PROVIDERS[provider]
            return keyring.get_password(KEYRING_SERVICE_NAME, cfg["keyring_key"]) is not None
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Save / delete
    # ------------------------------------------------------------------

    def set_session_key(self, provider: str, key: str) -> None:
        """Keep the key only for this running session (memory), never persisted."""
        self._session_keys[provider] = key

    def save_key(self, provider: str, key: str) -> Tuple[bool, str]:
        """Persist the key via the OS credential store (keyring)."""
        if not _KEYRING_AVAILABLE:
            return False, "keyring package not installed — cannot save securely. Run: pip install keyring"
        try:
            cfg = AI_MODE_PROVIDERS[provider]
            keyring.set_password(KEYRING_SERVICE_NAME, cfg["keyring_key"], key)
            self._session_keys[provider] = key
            return True, "API key saved securely."
        except Exception as exc:
            return False, f"Failed to save key: {exc}"

    def delete_key(self, provider: str) -> Tuple[bool, str]:
        """Remove any saved+session key for this provider ('reset-key')."""
        self._session_keys.pop(provider, None)
        if _KEYRING_AVAILABLE:
            try:
                cfg = AI_MODE_PROVIDERS[provider]
                keyring.delete_password(KEYRING_SERVICE_NAME, cfg["keyring_key"])
            except Exception:
                pass  # nothing saved, or backend unavailable — fine either way
        return True, "API key removed."

    def reset_all(self) -> None:
        for provider in AI_MODE_PROVIDERS:
            self.delete_key(provider)

    # ------------------------------------------------------------------
    # Validation — a small, cheap request to confirm the key actually works
    # before we ever save or rely on it.
    # ------------------------------------------------------------------

    def validate_key(self, provider: str, key: str) -> ValidationResult:
        key = (key or "").strip()
        if not key:
            return ValidationResult(False, "API key cannot be empty.")

        try:
            if provider == "openai":
                return self._validate_openai(key)
            if provider == "anthropic":
                return self._validate_anthropic(key)
            return ValidationResult(False, f"Unknown provider: {provider}")
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                return ValidationResult(False, "API key rejected (unauthorized). Check the key and try again.")
            return ValidationResult(False, f"Provider returned HTTP {exc.code}.")
        except urllib.error.URLError as exc:
            return ValidationResult(False, f"Could not reach provider (network error): {exc.reason}")
        except Exception as exc:
            return ValidationResult(False, f"Validation failed: {exc}")

    def _validate_openai(self, key: str) -> ValidationResult:
        req = urllib.request.Request(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {key}"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                return ValidationResult(True, "OpenAI key is valid.")
        return ValidationResult(False, "Unexpected response from OpenAI.")

    def _validate_anthropic(self, key: str) -> ValidationResult:
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/models",
            headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                return ValidationResult(True, "Anthropic key is valid.")
        return ValidationResult(False, "Unexpected response from Anthropic.")


# Single shared instance for the app's lifetime (mirrors get_tool_manager()).
_api_key_manager_instance: Optional[APIKeyManager] = None


def get_api_key_manager() -> APIKeyManager:
    global _api_key_manager_instance
    if _api_key_manager_instance is None:
        _api_key_manager_instance = APIKeyManager()
    return _api_key_manager_instance
