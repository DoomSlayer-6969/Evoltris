"""Game Theory engine interface (stub).

OPEN DESIGN QUESTION: the players, their strategy sets and the payoff
function have not been defined. No strategic model is implemented here on
purpose: inventing payoffs would add arbitrary behaviour without a
mathematical basis.

Once defined, an implementation receives a read-only ``GameObservation`` and
returns a ``StrategicAssessment``. The game loop will not depend on any
particular model.
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
    """Result of a strategic evaluation. Fields are to be defined with the model."""

    values: dict[str, float] = field(default_factory=dict)


class GameTheoryModel(Protocol):
    def evaluate(self, observation: GameObservation) -> StrategicAssessment: ...


class UndefinedGameTheoryModel:
    """Placeholder that refuses to run until a real model is specified."""

    def evaluate(self, observation: GameObservation) -> StrategicAssessment:
        raise NotImplementedError(
            "Game Theory model not yet specified: define players, strategies and payoffs."
        )
