# Design note

**Scope.** This demo schedules new routine primary-care and dermatology visits.
Its fixed date and in-memory clinic are intentional: the same patient script
must exercise the same slots before and after an improvement. It assumes the
patient is authenticated upstream and receives a fake patient reference in
session context. The agent does not collect extra identifiers or give medical
advice.

**Control and tools.** A small state machine owns conversation state and calls
two narrow clinic operations: search available slots and book an exact slot.
Only search results can be offered. Choosing an option creates a pending
selection; a clear yes creates a one-use backend token; booking checks that
token, patient context, and current availability. This keeps consent and
availability checks enforceable outside the language in the transcript.
Cancellation and rescheduling are explicit handoffs because the fixture has no
identity verification or change operation. Emergency phrase matches stop the
flow and direct the patient to emergency services.

**Evaluation and learning.** Nine scripted conversations cover booking, missing
details, unavailable and relative dates, consent ambiguity, medical questions,
unsupported cancellation, and two urgent-symptom cases. Assertions inspect both
transcripts and tool state. The baseline books after a patient discloses
emergency symptoms; this gap is deliberately seeded. Learning is split into
*analysis* (classify the failure, gather the failing transcripts) and *proposal*
(derive a candidate rule from that evidence). The default proposer is
deterministic and offline: it recognizes emergency *concepts* and synthesizes the
triggers from the words the patient actually used — so `R-001` is learned from
the run, not copied from a pre-authored phrase list (the seed memory ships
empty). An opt-in LLM proposer (`--propose llm`) does the same with no lexicon.
Critically, the proposer only chooses *which phrases escalate*; the action and
response are system-fixed and the regression gate decides promotion. The
candidate must raise the weighted score and preserve every previously passing
scenario before it is saved. The repeated run scores 9/9 (100%), up from 7/9
(53.8%); all seven passing cases stay green. `test_learning.py` asserts an unseen
phrasing is learned and the gate holds. Full traces are in `runs/latest.json`.

**Limits and judgment.** Concept matching and a tiny clinic fixture demonstrate
the closed loop; they are not ready for patients. The harness cannot measure
every unseen phrasing, real clinic policy, or clinical appropriateness. I kept
the agent's control path deterministic so the safety property and its
before/after result stay reproducible offline, and I deliberately did **not** let
a model rewrite policy or code. In a clinical workflow unconstrained
self-modification is a liability: a model can *propose* a new escalation trigger
from observed failures, but it cannot promote its own behavior, cannot choose the
action, and every learned change must improve the target failure without
introducing a new one. That is why learning is split into a proposer (deterministic
by default, LLM optional) and a regression gate that owns promotion. AI tools
helped scaffold and inspect the implementation; I kept the repair schema, the
proposer/gate separation, the safety boundary, and tool-level confirmation
explicit by my own judgment.
