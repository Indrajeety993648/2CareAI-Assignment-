"""A tiny in-memory clinic API used by the agent and its evaluator.

The API is deliberately authoritative: the agent can only offer slots returned
by search, and booking requires a one-use confirmation token created after an
explicit patient confirmation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class Slot:
    id: str
    specialty: str
    starts_at: datetime

    def label(self) -> str:
        return f"{self.starts_at.strftime('%a, %b')} {self.starts_at.day} at {self.starts_at.strftime('%I:%M %p').lstrip('0')}"


FIXED_TODAY = date(2026, 10, 7)
FIXTURE_SLOTS = (
    Slot("PC-101", "primary care", datetime(2026, 10, 12, 9, 0)),
    Slot("PC-102", "primary care", datetime(2026, 10, 12, 13, 30)),
    Slot("PC-103", "primary care", datetime(2026, 10, 14, 10, 0)),
    Slot("DE-201", "dermatology", datetime(2026, 10, 13, 11, 0)),
    Slot("PC-104", "primary care", datetime(2026, 10, 16, 15, 0)),
    Slot("PC-105", "primary care", datetime(2026, 10, 19, 8, 30)),
)


class ClinicAPI:
    """Fake clinic backend with auditable calls and a minimal consent boundary."""

    def __init__(self, patient_ref: str = "demo-patient-001") -> None:
        self.patient_ref = patient_ref
        self._slots = {slot.id: slot for slot in FIXTURE_SLOTS}
        self._booked: dict[str, dict[str, Any]] = {}
        self._confirmations: dict[str, str] = {}
        self.calls: list[dict[str, Any]] = []

    def search_slots(self, specialty: str, preferred_date: date | None = None) -> list[Slot]:
        candidates = [
            slot for slot in self._slots.values()
            if slot.specialty == specialty and slot.id not in self._booked
        ]
        if preferred_date is not None:
            exact = [slot for slot in candidates if slot.starts_at.date() == preferred_date]
            if exact:
                candidates = exact
            elif candidates:
                nearest_distance = min(abs((slot.starts_at.date() - preferred_date).days) for slot in candidates)
                candidates = [
                    slot for slot in candidates
                    if abs((slot.starts_at.date() - preferred_date).days) <= nearest_distance + 2
                ]
        candidates.sort(key=lambda slot: slot.starts_at)
        result = candidates[:3]
        self.calls.append({
            "tool": "search_slots",
            "specialty": specialty,
            "preferred_date": preferred_date.isoformat() if preferred_date else None,
            "returned_slot_ids": [slot.id for slot in result],
        })
        return result

    def get_slot(self, slot_id: str) -> Slot | None:
        return self._slots.get(slot_id)

    def authorize_booking(self, slot_id: str, explicit_yes: bool) -> str:
        """Mint a one-use token only when the controller has parsed a clear yes."""
        if not explicit_yes or slot_id not in self._slots:
            raise PermissionError("A clear confirmation for a real slot is required.")
        token = str(uuid4())
        self._confirmations[token] = slot_id
        self.calls.append({"tool": "record_confirmation", "slot_id": slot_id})
        return token

    def book_appointment(self, slot_id: str, patient_ref: str, confirmation_token: str) -> dict[str, Any]:
        authorized_slot = self._confirmations.pop(confirmation_token, None)
        if authorized_slot != slot_id:
            raise PermissionError("Booking requires a confirmation token for this exact slot.")
        if patient_ref != self.patient_ref:
            raise PermissionError("The patient context is not authorized for this booking.")
        slot = self._slots.get(slot_id)
        if slot is None:
            raise ValueError("Unknown slot.")
        if slot_id in self._booked:
            raise ValueError("That slot is no longer available.")
        appointment = {
            "appointment_id": f"APT-{len(self._booked) + 1:03d}",
            "patient_ref": patient_ref,
            "slot_id": slot.id,
            "specialty": slot.specialty,
            "starts_at": slot.starts_at.isoformat(timespec="minutes"),
        }
        self._booked[slot_id] = appointment
        self.calls.append({"tool": "book_appointment", **appointment, "confirmed": True})
        return appointment

    @property
    def bookings(self) -> list[dict[str, Any]]:
        return list(self._booked.values())

