import json
import time
from pathlib import Path
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class AgentState(BaseModel):
    ticker: str
    created_at: float = Field(default_factory=lambda: time.time())
    updated_at: float = Field(default_factory=lambda: time.time())
    step: str = "start"
    data_paths: Dict[str, str] = Field(default_factory=dict)
    notes: Dict[str, Any] = Field(default_factory=dict)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.updated_at = time.time()
        with path.open("w") as f:
            json.dump(self.dict(), f, indent=2)

    @staticmethod
    def load(path: Path) -> Optional["AgentState"]:
        if not path.exists():
            return None
        with path.open() as f:
            data = json.load(f)
        return AgentState(**data)


class Checkpointer:
    def __init__(self, base_dir: Path, ticker: str, save_every_seconds: int = 120):
        self.base_dir = base_dir
        self.ticker = ticker.upper()
        self.save_every_seconds = save_every_seconds
        self.state_path = base_dir / "output" / self.ticker / "state.json"
        self.last_saved = 0.0
        self.state = AgentState(ticker=self.ticker)

    def maybe_load(self, resume: bool) -> AgentState:
        if resume:
            existing = AgentState.load(self.state_path)
            if existing:
                self.state = existing
        return self.state

    def touch(self):
        now = time.time()
        if (now - self.last_saved) >= self.save_every_seconds:
            self.state.save(self.state_path)
            self.last_saved = now

    def save_now(self):
        self.state.save(self.state_path)
        self.last_saved = time.time()
