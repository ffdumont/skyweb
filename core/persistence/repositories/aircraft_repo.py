"""Repository for aircraft."""

from __future__ import annotations

from core.contracts.aircraft import Aircraft
from core.persistence.repositories.base import BaseRepository


class AircraftRepository(BaseRepository[Aircraft]):
    def __init__(self):
        super().__init__(Aircraft, "aircraft")
