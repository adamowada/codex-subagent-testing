from __future__ import annotations

import importlib.util
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
V2_TEMPLATE = REPO_ROOT / "benchmark_template_v2"
SEMANTICS_PATH = V2_TEMPLATE / "docs" / "ruleledger_v2_semantics.md"
EXAMPLES_PATH = V2_TEMPLATE / "fixtures" / "public_semantics_examples.json"
PLACEHOLDER_CASE_PATH = REPO_ROOT / "hidden_tests" / "cases_v2_placeholder" / "v2_placeholder.json"
GENERATOR_CONTRACT_PATH = REPO_ROOT / "hidden_tests" / "generators" / "ruleledger_v2_semantics.py"


def test_v2_semantics_document_is_visible_from_starter_readme() -> None:
    readme = (V2_TEMPLATE / "README.md").read_text(encoding="utf-8")
    examples = json.loads(EXAMPLES_PATH.read_text(encoding="utf-8"))

    assert SEMANTICS_PATH.exists()
    assert "docs/ruleledger_v2_semantics.md" in readme
    assert "fixtures/public_semantics_examples.json" in readme
    assert examples["semantics_document"] == "docs/ruleledger_v2_semantics.md"


def test_v2_semantics_rule_ids_cover_required_hard_mode_areas() -> None:
    semantics = SEMANTICS_PATH.read_text(encoding="utf-8")
    required_prefixes = {
        "BT": "bitemporal behavior",
        "OR": "replay ordering",
        "CV": "corrections and voids",
        "LC": "lifecycle precedence",
        "MG": "account merges",
        "BL": "billing and proration",
        "RP": "reporting and CSV stability",
        "PY": "TypeScript/Python parity",
    }

    for prefix in required_prefixes:
        assert f"### {prefix}-" in semantics, required_prefixes[prefix]

    required_fields = [
        "effectiveAt",
        "recordedAt",
        "sequence",
        "currency",
        "quantity",
        "seatDelta",
        "mergeFromAccountId",
        "correctionOf",
        "voidedEventId",
        "invoiceId",
        "periodStart",
        "periodEnd",
    ]
    for field in required_fields:
        assert field in semantics


def test_public_semantics_examples_cover_stage16_done_criteria() -> None:
    semantics = SEMANTICS_PATH.read_text(encoding="utf-8")
    examples = json.loads(EXAMPLES_PATH.read_text(encoding="utf-8"))["examples"]
    concepts = {example["concept"] for example in examples}

    assert concepts == {"bitemporal", "correction_void", "account_merge", "proration", "csv_parity"}
    for example in examples:
        assert example["rule_ids"], example["id"]
        for rule_id in example["rule_ids"]:
            assert f"### {rule_id}:" in semantics


def test_v2_placeholder_cases_reference_documented_semantics_rules() -> None:
    semantics = SEMANTICS_PATH.read_text(encoding="utf-8")
    payload = json.loads(PLACEHOLDER_CASE_PATH.read_text(encoding="utf-8"))

    for case in payload["cases"]:
        assert case["rule_ids"], case["id"]
        for rule_id in case["rule_ids"]:
            assert f"### {rule_id}:" in semantics


def test_generator_side_v2_contract_references_documented_rules_and_fields() -> None:
    semantics = SEMANTICS_PATH.read_text(encoding="utf-8")
    contract = _load_generator_contract()

    for rule_ids in contract.V2_RULE_IDS.values():
        for rule_id in rule_ids:
            assert f"### {rule_id}:" in semantics

    for field in contract.V2_SUMMARY_FIELDS:
        assert field in semantics

    header = ",".join(contract.V2_CSV_HEADER)
    assert header in semantics


def _load_generator_contract():
    spec = importlib.util.spec_from_file_location("ruleledger_v2_semantics", GENERATOR_CONTRACT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
