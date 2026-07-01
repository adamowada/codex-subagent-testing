from __future__ import annotations

from typing import Mapping


STAGED_LEAF_ASSIGNMENT_SETS: dict[str, tuple[dict[str, str], ...]] = {
    "six_role": (
        {
            "id": "leaf_01",
            "title": "TypeScript parsing, normalization, views, and migration compatibility",
            "focus": "TypeScript parse/normalize/view compatibility, v2 migration behavior, and public API stability.",
        },
        {
            "id": "leaf_02",
            "title": "TypeScript replay, billing, reporting, performance, and API integration",
            "focus": "TypeScript replay model, billing/proration, reporting, performance shape, and exports.",
        },
        {
            "id": "leaf_03",
            "title": "Python parsing, normalization, views, and migration compatibility",
            "focus": "Python parse/normalize/view compatibility, v2 migration behavior, and public API stability.",
        },
        {
            "id": "leaf_04",
            "title": "Python replay, billing, reporting, performance, and API integration",
            "focus": "Python replay model, billing/proration, reporting, performance shape, and exports.",
        },
        {
            "id": "leaf_05",
            "title": "Cross-language parity, fixtures, public tests, and regression review",
            "focus": "TypeScript/Python parity risks, visible regression tests, deterministic CSV output, and fixture review.",
        },
        {
            "id": "leaf_06",
            "title": "Adversarial localization, maintainability, performance, and hidden-test risk review",
            "focus": "Architectural localization, maintainability hazards, performance traps, and hidden-test risk analysis.",
        },
    ),
    "three_role": (
        {
            "id": "leaf_01",
            "title": "TypeScript implementation surface",
            "focus": "TypeScript parsing, normalization, replay, billing, reporting, public API compatibility, and performance.",
        },
        {
            "id": "leaf_02",
            "title": "Python implementation surface",
            "focus": "Python parsing, normalization, replay, billing, reporting, public API compatibility, and performance.",
        },
        {
            "id": "leaf_03",
            "title": "Cross-language parity, regression, performance, and adversarial review",
            "focus": "TypeScript/Python parity, fixtures, visible tests, deterministic outputs, performance traps, and hidden-test risk.",
        },
    ),
}


def staged_assignment_set_name(leaf: Mapping[str, object] | None) -> str:
    if not leaf:
        return "six_role"
    value = leaf.get("assignment_set")
    return str(value) if value else "six_role"


def staged_leaf_assignments(leaf: Mapping[str, object] | None) -> tuple[dict[str, str], ...]:
    return STAGED_LEAF_ASSIGNMENT_SETS.get(staged_assignment_set_name(leaf), STAGED_LEAF_ASSIGNMENT_SETS["six_role"])


def render_staged_leaf_assignments(leaf: Mapping[str, object] | None) -> str:
    return "\n".join(
        f"{index}. {assignment['title']}. Focus: {assignment['focus']}"
        for index, assignment in enumerate(staged_leaf_assignments(leaf), start=1)
    )
