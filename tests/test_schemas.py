from decimal import Decimal

import pytest
from pydantic import ValidationError

from metso_agent.schemas import (
    AgentResponse,
    CostItem,
    EvidenceStatus,
    FlotationStatistic,
    ProductEvidence,
    ServiceReport,
    SourceRef,
)


# -----------------------------------------
# Synthetic source for testing only
# -----------------------------------------

def sample_report_source():
    return SourceRef(
        source_kind="service_report",
        document_id="FSR-9999",
    )


# -----------------------------------------
# Product evidence tests
# -----------------------------------------

def test_product_evidence_has_page():

    entry = ProductEvidence(
        product_name="Demo Filter",
        chunk_id="demo-p2-c1",
        excerpt="Synthetic text only",
        source=SourceRef(
            source_kind="brochure",
            document_id="demo-filter",
            page_number=2,
        ),
    )

    assert entry.source.page_number == 2


def test_product_evidence_missing_page_rejected():

    with pytest.raises(ValidationError):

        ProductEvidence(
            product_name="Demo Filter",
            chunk_id="c1",
            excerpt="Synthetic",
            source=SourceRef(
                source_kind="brochure",
                document_id="demo-filter",
            ),
        )


# -----------------------------------------
# Cost calculation tests
# -----------------------------------------

def test_cost_item_calculates_derived_amount():

    item = CostItem(
        category="parts",
        description="Synthetic replacement piece",
        quantity=Decimal("3"),
        unit="piece",
        unit_rate=Decimal("12.50"),
        currency="EUR",
        source=sample_report_source(),
    )

    assert item.derived_amount() == Decimal("37.50")


def test_missing_rate_is_not_zero():

    item = CostItem(
        category="parts",
        description="Unpriced synthetic part",
        quantity=Decimal("3"),
        currency="EUR",
        source=sample_report_source(),
    )

    assert item.derived_amount() is None


def test_unknown_currency_prevents_derived_amount():

    item = CostItem(
        category="labor",
        description="Synthetic labor",
        quantity=Decimal("2"),
        unit="hour",
        unit_rate=Decimal("80"),
        source=sample_report_source(),
    )

    assert item.derived_amount() is None


def test_negative_quantity_rejected():

    with pytest.raises(ValidationError):

        CostItem(
            category="parts",
            description="Synthetic part",
            quantity=Decimal("-2"),
            source=sample_report_source(),
        )


def test_bad_currency_rejected():

    with pytest.raises(ValidationError):

        CostItem(
            category="parts",
            description="Synthetic part",
            currency="euros",
            source=sample_report_source(),
        )


# -----------------------------------------
# Service report tests
# -----------------------------------------

def test_report_can_have_unknown_cost():

    report = ServiceReport(
        report_id="FSR-9999",
        source=sample_report_source(),
        equipment_model="Demo machine",
    )

    assert report.reported_total is None
    assert report.cost_items == []


def test_report_id_mismatch_rejected():

    with pytest.raises(ValidationError):

        ServiceReport(
            report_id="FSR-1000",
            source=sample_report_source(),
        )


# -----------------------------------------
# Agent response tests
# -----------------------------------------

def test_supported_answer_requires_evidence():

    with pytest.raises(ValidationError):

        AgentResponse(
            answer="A fully sourced claim",
            routes=["product"],
            status=EvidenceStatus.SUPPORTED,
        )


def test_partial_answer_can_ask_question():

    response = AgentResponse(
        answer="There is not enough verified price evidence.",
        routes=["service_cost"],
        status=EvidenceStatus.PARTIAL,
        clarification_question=(
            "Who will provide the replacement parts?"
        ),
    )

    assert response.status == EvidenceStatus.PARTIAL


# -----------------------------------------
# Flotation statistics tests
# -----------------------------------------

def test_flotation_statistic_has_source_and_sample_size():

    metric = FlotationStatistic(
        metric="synthetic mean",
        value=Decimal("12.5"),
        sample_size=10,
        source=SourceRef(
            source_kind="flotation",
            document_id="synthetic.csv",
        ),
    )

    assert metric.sample_size == 10


def test_flotation_statistic_rejects_wrong_source():

    with pytest.raises(ValidationError):

        FlotationStatistic(
            metric="synthetic mean",
            value=Decimal("12.5"),
            sample_size=10,
            source=sample_report_source(),
        )