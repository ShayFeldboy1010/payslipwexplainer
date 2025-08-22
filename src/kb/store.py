"""In-memory knowledge base."""
from typing import Dict

class KnowledgeBase:
    """Store slip text by id."""
    def __init__(self) -> None:
        self._store: Dict[str, str] = {}

    def add(self, slip_id: str, text: str) -> None:
        self._store[slip_id] = text

    def get(self, slip_id: str) -> str:
        return self._store.get(slip_id, "")

    @property
    def store(self) -> Dict[str, str]:
        return self._store
