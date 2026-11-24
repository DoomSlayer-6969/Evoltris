"""Game Theory engine interface.

A model receives a read-only ``GameObservation`` and returns a
``StrategicAssessment``. The implementation is the zero-sum player-vs-director
game in ``strategy/director.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import numpy as np


@dataclass(frozen=True)
class GameObservation:
    """Read-only snapshot of the game state offered to strategic models."""

    board: np.ndarray
    life_grid: np.ndarray
    cml_state: np.ndarray
    score: int
    lines: int
    level: int


@dataclass(frozen=True)
class StrategicAssessment:
    """Result of a strategic evaluation, as named values (e.g. equilibrium mixes)."""

    values: dict[str, float] = field(default_factory=dict)


class GameTheoryModel(Protocol):
    def evaluate(self, observation: GameObservation) -> StrategicAssessment: ...
