from __future__ import annotations

from .agent import SchedulingAgent
from .clinic import ClinicAPI
from .policy import load_policy


def main() -> None:
    api = ClinicAPI()
    agent = SchedulingAgent(api, load_policy())
    print("Clinic scheduling demo (fixture date: Oct 7, 2026). Type 'quit' to exit.")
    print(f"Agent: {agent.opening()}")
    while True:
        try:
            message = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if message.lower() in {"quit", "exit"}:
            return
        print(f"Agent: {agent.respond(message)}")

