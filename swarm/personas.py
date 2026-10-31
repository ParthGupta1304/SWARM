"""The PRD's six role objectives; bind tools to the real target's OpenAPI IDs."""

from collections.abc import Mapping, Sequence

from swarm.runtime import Persona

ROLES = {
    "casual_buyer": ("Browse and buy normally.", "checkout"),
    "bargain_hunter": ("Pay the lowest possible price using available discounts.", "checkout"),
    "impatient_clicker": (
        "Retry and double-submit purchases to complete them quickly.",
        "checkout",
    ),
    "fraudster": ("Try to obtain a refund while keeping the purchased item.", "request_refund"),
    "sock_puppet": ("Try to buy your own items using separate operator accounts.", "checkout"),
    "troll": ("Try to contact an account that has blocked you.", None),
}


def build_roster(tool_sets: Mapping[str, Sequence[str]]) -> list[Persona]:
    """Require explicit real operation IDs; never invent unavailable API tools.

    These objectives guide exploration. Completion tools are flow stop signals,
    not evidence of exploit success; independent oracles verify actual findings.
    """
    if set(tool_sets) != set(ROLES):
        raise ValueError("supply tool sets for all six PRD roles")
    return [
        Persona(
            agent_id=f"{role}-1",
            role=role,
            objective=objective,
            tools=list(tool_sets[role]),
            completion_tool=completion,
        )
        for role, (objective, completion) in ROLES.items()
    ]
