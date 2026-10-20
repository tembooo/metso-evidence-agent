"""Stage 08 quote-guard regressions; uses only synthetic sample records."""
import pytest
from metso_agent.validation.response_guard import validate_answer

EVIDENCE = {
    'status': 'INSUFFICIENT_EVIDENCE_FOR_SITE_SPECIFIC_QUOTE',
    'site_specific_budget': None,
    'task_analogs': [{'report_id': 'FSR-0001'}],
    'best_historical_analog': {
        'report_id': 'FSR-0001',
        'reconstructed': {'amount': '120.00', 'currency': 'EUR'},
        'components': [{'description': 'labor', 'amount': '120.00', 'currency': 'EUR'}],
    },
    'local_historical_rates_other_scopes': [],
}

def check(answer):
    return validate_answer(answer, [('compare_service_costs', EVIDENCE)])

@pytest.mark.parametrize('answer', [
    'This cannot be treated as an official Chile budget.',
    'This is not a confirmed or official Chile quotation.',
    'Do not interpret this as a binding Chile price.',
    'This figure isn\'t a confirmed Chile quote.',
    'The official Chile quote has not been issued.',
    'FSR-0001 has a provisional sum of 120.00 EUR, not an official Chile quote.',
])
def test_explicit_absence_is_not_false_quote(answer):
    assert check(answer).ok, check(answer).issues

@pytest.mark.parametrize('answer', [
    'The official Chile quote is 120.00 EUR.',
    'This is not an official Chile quote, but the confirmed Chile quote is 120.00 EUR.',
    'This is not an official Chile quote. However, the binding Chile price is 120.00 EUR.',
    'The final Chile quote has been approved.',
])
def test_affirmative_quote_still_blocked(answer):
    assert 'UNSUPPORTED_SITE_SPECIFIC_QUOTE' in check(answer).issues


def test_unsupported_amount_still_blocked():
    result = check('The historical amount was 9,999.00 EUR, not an official Chile quote.')
    assert 'UNSUPPORTED_MONETARY_AMOUNT' in result.issues


def test_supported_analog_no_site_claim():
    assert check('FSR-0001 shows a historical 120.00 EUR component total. This is not a Chile quotation.').ok
