"""Stage 07: bounded, conservative post-generation evidence checks.

This is a deterministic safety gate, not a semantic entailment oracle.
It verifies that cited references were returned, explicitly monetary numbers
are grounded or reconstructible, and no site-specific quote is manufactured.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re
from typing import Any

REPORT = re.compile(r"\bFSR-\d{4}\b", re.I)
BROCHURE_CITATION = re.compile(
    r"\b([a-z][a-z0-9]*(?:-[a-z0-9]+)+)(?:\.md)?\s*[,;:]?\s*"
    r"(?:p\.?|page)\s*(\d+)\b", re.I
)
AMOUNT = re.compile(
    r"(?<![\w])(?:\b(EUR|USD|CAD|SEK|AUD|ZAR)\s*"
    r"([\d][\d,]*(?:\.\d{1,2})?)|"
    r"([\d][\d,]*(?:\.\d{1,2})?)\s*\b(EUR|USD|CAD|SEK|AUD|ZAR)\b)", re.I
)
EURO_SYMBOL = re.compile(r"€\s*([\d][\d,]*(?:\.\d{1,2})?)")
MIXED_CURRENCY_ADDITION = re.compile(
    r"(?:\d[\d,.]*\s*(EUR|USD|CAD|SEK|AUD|ZAR))\s*\+\s*"
    r"(?:\d[\d,.]*\s*(EUR|USD|CAD|SEK|AUD|ZAR))", re.I
)
UNSUPPORTED_GUARANTEE = re.compile(
    r"\b(?:guarantee(?:d)?|promise(?:d)?|certain(?:ly)?)\b.{0,90}"
    r"\b(?:\d+(?:\.\d+)?\s*%|saving|improvement|compatib|perform)", re.I | re.S
)


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    issues: tuple[str, ...]


def _amount(value: Any) -> Decimal | None:
    try:
        parsed = Decimal(str(value).replace(",", ""))
        return parsed.quantize(Decimal("0.01")) if parsed.is_finite() else None
    except (InvalidOperation, TypeError, ValueError):
        return None


def _collect_supported_money(cost: dict) -> dict[str, set[Decimal]]:
    supported: dict[str, set[Decimal]] = {}

    def record(value: Any, currency: Any) -> None:
        if not isinstance(currency, str) or not re.fullmatch(r"[A-Z]{3}", currency):
            return
        number = _amount(value)
        if number is not None:
            supported.setdefault(currency, set()).add(number)

    best = cost.get("best_historical_analog") or {}
    components = best.get("components") or []
    for item in components:
        record(item.get("amount"), item.get("currency"))
        record(item.get("unit_rate"), item.get("currency"))
    reconstructed = best.get("reconstructed") or {}
    record(reconstructed.get("amount"), reconstructed.get("currency"))
    record(best.get("printed_total"), best.get("printed_currency"))
    for item in cost.get("task_analogs") or []:
        record(item.get("source_printed_total"), item.get("source_printed_currency"))
    for rec in cost.get("local_historical_rates_other_scopes") or []:
        for item in rec.get("observations", rec.get("rates", [])) or []:
            record(item.get("hourly_rate"), item.get("currency"))
    # Derived, transparent sum when a customer explicitly supplies replacement cloths.
    # This is an arithmetic historical comparator, NOT an authorized Chile quote.
    original = reconstructed.get("currency")
    if original and components:
        base = _amount(reconstructed.get("amount"))
        if base is not None:
            for item in components:
                if re.search(r"\bcloths?\b", str(item.get("description", "")), re.I):
                    deduction = _amount(item.get("amount"))
                    if deduction is not None and item.get("currency") == original and base >= deduction:
                        record(base - deduction, original)
    return supported


# STAGE09_GUARANTEE_NEGATION_V1
# Classify promises separately per clause, preserving an affirmative promise
# after a rejected or negated promise in the same response.
def _asserts_unsupported_guarantee(answer: str) -> bool:
    clauses = re.split(r"(?<!\d)\.(?!\d)|[!?;\n]|\b(?:but|however|yet|although|nevertheless)\b", answer, flags=re.I)
    for clause in clauses:
        for match in UNSUPPORTED_GUARANTEE.finditer(clause):
            preceding = clause[max(0, match.start() - 90): match.start()]
            denial = re.search(
                r"\b(?:cannot|can\s+not|can't|do\s+not|don't|does\s+not|doesn't|"
                r"will\s+not|won't|never|no|not|unable\s+to|not\s+able\s+to)\b"
                r"(?:\s+[\w'-]+){0,5}\s*$", preceding, flags=re.I,
            )
            if not denial:
                return True
    return False


def validate_answer(answer: str, tool_results: list[tuple[str, dict]]) -> ValidationResult:
    if not isinstance(answer, str) or not answer.strip():
        return ValidationResult(False, ("EMPTY_ANSWER",))
    problems: list[str] = []
    brochures: set[tuple[str, int]] = set()
    reports: set[str] = set()
    money: dict[str, set[Decimal]] = {}
    cost_available = False
    for name, output in tool_results:
        if not isinstance(output, dict):
            problems.append("MALFORMED_TOOL_RESULT")
            continue
        if output.get("status") == "TOOL_ERROR":
            problems.append("TOOL_EXECUTION_ERROR")
        if name == "search_product_brochures":
            for item in output.get("items", []):
                if isinstance(item.get("page"), int) and isinstance(item.get("source_id"), str):
                    brochures.add((item["source_id"].casefold(), item["page"]))
        elif name == "compare_service_costs":
            cost_available = True
            for hit in output.get("task_analogs") or []:
                if hit.get("report_id"):
                    reports.add(str(hit["report_id"]).upper())
            best = output.get("best_historical_analog") or {}
            if best.get("report_id"):
                reports.add(str(best["report_id"]).upper())
            for hit in output.get("local_historical_rates_other_scopes") or []:
                if hit.get("report_id"):
                    reports.add(str(hit["report_id"]).upper())
            for currency, values in _collect_supported_money(output).items():
                money.setdefault(currency, set()).update(values)
            if output.get("site_specific_budget") is None:
                # Ban affirmative descriptions of a current/confirmed Chile quote.
                # STAGE08_QUOTE_NEGATION_FIX_V1
                # Examine EACH potential quote claim, not just the first one.
                # Explicitly negative statements must be allowed (we have no quote),
                # but any affirmative claim for an unsupported site remains blocked.
                quote_pattern = (r"\b(?:confirmed|final|official|binding|verified)\s+"
                                 r"(?:chile(?:an)?\s+)?(?:quote|quotation|price|budget)\b")
                for quote_claim in re.finditer(quote_pattern, answer, re.I):
                    preceding = answer[max(0, quote_claim.start() - 140):quote_claim.start()]
                    # Keep negations local to their clause: "not ...; but confirmed ..."
                    # must never let the earlier "not" excuse the later claim.
                    clause = re.split(r"[.!?;:,\n]|\b(?:but|however|yet)\b", preceding, flags=re.I)[-1]
                    negated_before = bool(re.search(
                        r"\b(?:not|never|no|cannot|can't|isn't|aren't|wasn't|weren't|"
                        r"don't|doesn't|didn't|shouldn't|mustn't|without)\b"
                        r"(?:\s+[\w'-]+){0,12}\s*$", clause, re.I))
                    trailing = answer[quote_claim.end():quote_claim.end() + 75]
                    negated_after = bool(re.match(
                        r"\s+(?:(?:is|was|remains)\s+(?:not\s+(?:available|known|"
                        r"confirmed|established|provided)|unavailable|unknown|unconfirmed)|"
                        r"has\s+not\s+(?:been\s+)?(?:issued|provided|established))\b",
                        trailing, re.I))
                    if not (negated_before or negated_after):
                        problems.append("UNSUPPORTED_SITE_SPECIFIC_QUOTE")
                        break
                if re.search(r"\b(?:Chile(?:an)?|Antofagasta)\s+(?:service\s+)?"
                             r"(?:price|quote|budget)\s+(?:is|equals|will be)\s*"
                             r"(?:EUR|USD|\$|€|\d)", answer, re.I):
                    problems.append("UNSUPPORTED_SITE_SPECIFIC_QUOTE")
    for report_id in set(x.upper() for x in REPORT.findall(answer)):
        if report_id not in reports:
            problems.append("UNKNOWN_SERVICE_CITATION")
    for stem, page in BROCHURE_CITATION.findall(answer):
        # Only treat hyphenated document refs followed by p.N as a citation.
        if (stem.casefold(), int(page)) not in brochures:
            problems.append("UNKNOWN_BROCHURE_PAGE")
    for match in EURO_SYMBOL.finditer(answer):
        num = _amount(match.group(1))
        if num is not None and num not in money.get("EUR", set()):
            approx = bool(re.search(r"(?:about|around|approximately|≈|~)\s*$", answer[max(0, match.start()-25):match.start()], re.I))
            if not (approx and num == num.to_integral_value() and any(abs(num - x) <= Decimal("0.50") for x in money.get("EUR", set()))):
                problems.append("UNSUPPORTED_MONETARY_AMOUNT")
    for match in AMOUNT.finditer(answer):
        currency = (match.group(1) or match.group(4)).upper()
        num = _amount(match.group(2) or match.group(3))
        if num is not None and num not in money.get(currency, set()):
            approx = bool(re.search(r"(?:about|around|approximately|≈|~)\s*$", answer[max(0, match.start()-25):match.start()], re.I))
            rounded_match = bool(approx and num == num.to_integral_value() and any(abs(num - x) <= Decimal("0.50") for x in money.get(currency, set())))
            if not rounded_match:
                problems.append("UNSUPPORTED_MONETARY_AMOUNT")
    for left, right in MIXED_CURRENCY_ADDITION.findall(answer):
        if left.upper() != right.upper():
            problems.append("MIXED_CURRENCY_ADDITION")
    # Preserve guard against positive guarantees while allowing explicit denial.
    if _asserts_unsupported_guarantee(answer):
        problems.append("UNSUPPORTED_PERFORMANCE_GUARANTEE")
    return ValidationResult(not problems, tuple(dict.fromkeys(problems)))
