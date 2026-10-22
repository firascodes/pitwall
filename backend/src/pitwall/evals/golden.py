"""The golden set for the agent: questions with the tools, facts and components a good answer needs.

Facts were read from the graph with the tools directly (no LLM), for the 2026 season to round 17.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Case:
    question: str
    tools: set[str]  # must all be called; extra calls are allowed
    facts: list[str]  # each must appear in the answer (case-insensitive); "3|three" = either
    components: set[str] = field(default_factory=set)


CASES = [
    Case("Who leads the drivers' championship?", {"standings"}, ["Antonelli", "340"]),
    Case("Which team leads the constructors' championship?", {"standings"}, ["Mercedes", "578"]),
    Case(
        "Who took pole position in Monaco, and with what time?",
        {"session_results"},
        ["Antonelli", "1:12.051"],
    ),
    Case("Who won the Singapore Grand Prix?", {"session_results"}, ["Verstappen"]),
    Case(
        "What is Antonelli's qualifying head-to-head against Russell?",
        {"teammate_battle"},
        ["10", "7"],
    ),
    Case(
        "Which teams has Liam Lawson driven for this season?", {"driver_teams"}, ["Red Bull", "RB"]
    ),
    Case("How many laps were deleted in Monza qualifying?", {"session_laps"}, ["3|three"]),
    Case(
        "Compare Hamilton and Leclerc's fastest laps in Singapore qualifying",
        {"find_lap", "compare_laps"},
        ["1:31.427", "1:31.496"],
        {"lap_replay", "delta_chart", "corner_table"},
    ),
]
