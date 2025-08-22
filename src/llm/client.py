"""Minimal OpenAI-compatible client for Groq."""
import os

class GroqClient:
    """Placeholder Groq client returning canned responses."""
    def __init__(self, api_key: str | None = None, base_url: str | None = None, model: str = "openai/gpt-oss-20b") -> None:
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "")
        self.base_url = base_url or "https://api.groq.com/openai/v1"
        self.model = model

    def answer(self, prompt: str) -> str:
        """Return a dummy answer.

        Real integration would call the Groq API.
        """
        return "This is a placeholder answer."
