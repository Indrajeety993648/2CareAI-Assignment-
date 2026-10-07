"""Self-check: the loop learns an urgent escalation rule from run evidence —
including a phrase it was never pre-authored with — and the rule clears the
regression gate. Run: python test_learning.py"""

from scheduler.eval import evaluate, propose_reinforcement
from scheduler.policy import load_policy

baseline = evaluate(load_policy(use_reinforcements=False))
failed = [r for r in baseline["results"] if not r["passed"]]

rule = propose_reinforcement(failed)  # deterministic, offline
assert rule is not None, "analyzer found no supported repair"
assert rule["action"] == "stop_scheduling_and_escalate"
assert rule["proposed_by"] == "deterministic"

# Learned from THIS run's transcript, not a pre-written reinforcement:
# the seed memory (data/reinforcements.json) ships empty, yet the novel-phrasing
# scenario's words are now triggers.
assert "can't breathe" in rule["trigger_any"], rule["trigger_any"]
assert "feeling faint" in rule["trigger_any"], rule["trigger_any"]

# Promotion gate: candidate must improve and regress nothing.
candidate = load_policy(use_reinforcements=False)
candidate["safety_rules"] = [rule]
after = evaluate(candidate)
before_pass = {r["id"] for r in baseline["results"] if r["passed"]}
after_pass = {r["id"] for r in after["results"] if r["passed"]}
assert not (before_pass - after_pass), f"regression: {before_pass - after_pass}"
assert after["weighted_score"] > baseline["weighted_score"]

print(f"ok: learned {rule['trigger_any']}  "
      f"{baseline['weighted_score']}% -> {after['weighted_score']}%  (0 regressions)")
