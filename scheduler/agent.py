"""A bounded, multi-turn scheduler with explicit state and tool boundaries."""

from __future__ import annotations

import re
from datetime import date, timedelta
from .clinic import FIXED_TODAY, ClinicAPI


MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6,
    "jul": 7, "july": 7, "aug": 8, "august": 8, "sep": 9, "sept": 9,
    "september": 9, "oct": 10, "october": 10, "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}
WEEKDAYS = {name.lower(): i for i, name in enumerate(
    ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
)}
EMERGENCY_COPY = (
    "The symptoms you described may be an emergency. Please call 911 now or go to the nearest emergency department. "
    "I’m stopping appointment scheduling so you can get urgent help."
)


def parse_date(text: str, today: date = FIXED_TODAY) -> date | None:
    lowered = text.lower()
    iso = re.search(r"\b(202\d-\d{2}-\d{2})\b", lowered)
    if iso:
        try:
            return date.fromisoformat(iso.group(1))
        except ValueError:
            return None
    month_pattern = r"\b(" + "|".join(sorted(MONTHS, key=len, reverse=True)) + r")\.?\s+(\d{1,2})(?:st|nd|rd|th)?\b"
    match = re.search(month_pattern, lowered)
    if match:
        month, day = MONTHS[match.group(1)], int(match.group(2))
        year = today.year
        try:
            result = date(year, month, day)
        except ValueError:
            return None
        if result < today and not re.search(r"\b(last|past)\b", lowered):
            return date(year + 1, month, day)
        return result
    if "tomorrow" in lowered:
        return today + timedelta(days=1)
    if re.search(r"\btoday\b", lowered):
        return today
    weekday_match = re.search(r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", lowered)
    if weekday_match:
        weekday = WEEKDAYS[weekday_match.group(1)]
        delta = (weekday - today.weekday()) % 7
        if delta == 0:
            delta = 7
        if "next week" in lowered:
            days_until_monday = (7 - today.weekday()) % 7 or 7
            return today + timedelta(days=days_until_monday + weekday)
        return today + timedelta(days=delta)
    return None


def _contains_any(text: str, terms: list[str]) -> bool:
    lowered = text.lower()
    return any(term.lower() in lowered for term in terms)


class SchedulingAgent:
    def __init__(self, api: ClinicAPI, policy: dict) -> None:
        self.api = api
        self.policy = policy
        self.specialty: str | None = None
        self.preferred_date: date | None = None
        self.offered_slot_ids: list[str] = []
        self.pending_slot_id: str | None = None
        self.closed_for_safety = False
        self.last_offered_slot_ids: list[str] = []
        self.turns = 0

    @staticmethod
    def opening() -> str:
        return "I can help schedule a routine primary-care or dermatology visit. What type of visit and date would you prefer?"

    def respond(self, message: str) -> str:
        self.turns += 1
        if self.closed_for_safety:
            return "I’ve stopped scheduling this conversation. Please contact emergency services for urgent symptoms."

        if self._urgent(message):
            self.closed_for_safety = True
            self.pending_slot_id = None
            self.offered_slot_ids = []
            return EMERGENCY_COPY

        lowered = message.lower()
        if _contains_any(lowered, ["cancel", "reschedule", "move my appointment", "change my appointment"]):
            return "I can only schedule new routine visits in this demo. For a cancellation or change, please call the clinic so staff can verify and update your appointment."

        advice_preface = ""
        if _contains_any(lowered, ["do i need", "should i", "what does this", "is this serious", "which medicine", "what medication"]):
            advice_preface = "I can’t diagnose symptoms or advise on tests or medication. I can help arrange a visit. "

        if self.pending_slot_id:
            if self._negative(lowered):
                self.pending_slot_id = None
                return advice_preface + "Okay, I won’t book that. Would you like to look at a different date or time?"
            selected = self._select_offered(lowered)
            if selected:
                return advice_preface + self._select_or_book(selected, self._explicit_consent(lowered))
            if self._affirmative(lowered):
                return advice_preface + self._book(self.pending_slot_id)
            # A changed date or specialty is a new preference, so discard the old offer.
            parsed_specialty = self._parse_specialty(lowered)
            parsed_date = parse_date(lowered)
            if parsed_specialty or parsed_date:
                self.pending_slot_id = None
                self.offered_slot_ids = []
            else:
                slot = self.api.get_slot(self.pending_slot_id)
                return advice_preface + f"Please confirm: should I book {slot.specialty} on {slot.label()}? Say yes to book it, or no to keep looking."

        # A selection is meaningful only against the last tool-backed offer.
        # Process it before searching again so a follow-up such as "option 2"
        # cannot silently replace the offered choices with a fresh result set.
        selected = self._select_offered(lowered)
        if selected:
            return advice_preface + self._select_or_book(selected, self._explicit_consent(lowered))

        if not self.specialty:
            self.specialty = self._parse_specialty(lowered)
        parsed_date = parse_date(lowered)
        if parsed_date:
            self.preferred_date = parsed_date

        if not self.specialty:
            return advice_preface + "Which visit would you like: primary care or dermatology? I can schedule routine visits only."
        if not self.preferred_date and not self.offered_slot_ids:
            return advice_preface + f"What date would you prefer for {self.specialty}? You can give a date or weekday."

        slots = self.api.search_slots(self.specialty, self.preferred_date)
        self.offered_slot_ids = [slot.id for slot in slots]
        self.last_offered_slot_ids = list(self.offered_slot_ids)
        if not slots:
            return advice_preface + f"I couldn’t find an opening for {self.specialty} in the fixture. Please call the clinic to check other dates."
        exact = self.preferred_date and any(slot.starts_at.date() == self.preferred_date for slot in slots)
        intro = "I found these openings:" if exact or not self.preferred_date else f"I don’t have an opening on {self.preferred_date.strftime('%b')} {self.preferred_date.day}. The nearest available options are:"
        choices = " ".join(f"{i}. {slot.label()}." for i, slot in enumerate(slots, 1))
        return advice_preface + intro + " " + choices + " Tell me an option number. I’ll ask you to confirm before booking."

    def _urgent(self, message: str) -> bool:
        for rule in self.policy.get("safety_rules", []):
            if rule.get("action") == "stop_scheduling_and_escalate" and _contains_any(message, rule.get("trigger_any", [])):
                return True
        return False

    @staticmethod
    def _parse_specialty(text: str) -> str | None:
        if _contains_any(text, ["primary care", "family medicine", "family doctor", "pcp"]):
            return "primary care"
        if _contains_any(text, ["dermatology", "dermatologist", "skin doctor"]):
            return "dermatology"
        return None

    def _select_offered(self, text: str) -> str | None:
        if not self.offered_slot_ids:
            return None
        if re.search(r"\b(earliest|first option|first one)\b", text):
            return self.offered_slot_ids[0]
        if re.search(r"\b(latest|last option|last one)\b", text):
            return self.offered_slot_ids[-1]
        match = re.search(r"\b(?:option|number|slot)?\s*(first|1st|1|second|2nd|2|third|3rd|3)\b", text)
        if match:
            labels = {"first": 1, "1st": 1, "1": 1, "second": 2, "2nd": 2, "2": 2, "third": 3, "3rd": 3, "3": 3}
            index = labels[match.group(1)] - 1
            return self.offered_slot_ids[index] if index < len(self.offered_slot_ids) else None
        for slot_id in self.offered_slot_ids:
            if slot_id.lower() in text:
                return slot_id
        return None

    @staticmethod
    def _explicit_consent(text: str) -> bool:
        if re.search(r"\b(no|don't|do not|without|not)\b", text):
            return False
        return bool(re.search(r"\b(yes|book|schedule|confirm|go ahead|please do it|that works)\b", text))

    @staticmethod
    def _affirmative(text: str) -> bool:
        return bool(re.match(r"^(yes|yeah|yep|correct|confirm|go ahead|please do)\b", text.strip()))

    @staticmethod
    def _negative(text: str) -> bool:
        return bool(re.match(r"^(no|nope|not that|different|never mind|cancel)\b", text.strip()))

    def _select_or_book(self, slot_id: str, consent: bool) -> str:
        if consent:
            return self._book(slot_id)
        self.pending_slot_id = slot_id
        slot = self.api.get_slot(slot_id)
        return f"I can book {slot.specialty} on {slot.label()}. Should I book that exact time? Say yes to confirm, or no to keep looking."

    def _book(self, slot_id: str) -> str:
        try:
            token = self.api.authorize_booking(slot_id, explicit_yes=True)
            appointment = self.api.book_appointment(slot_id, self.api.patient_ref, token)
        except (PermissionError, ValueError) as error:
            self.pending_slot_id = None
            return f"I couldn’t complete that booking: {error} Please choose another available time."
        slot = self.api.get_slot(slot_id)
        self.pending_slot_id = None
        return f"You’re booked for {slot.specialty} on {slot.label()}. Confirmation number {appointment['appointment_id']}."
