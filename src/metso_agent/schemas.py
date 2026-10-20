from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


# ---------------------------------------------
# Evidence status
# ---------------------------------------------

class EvidenceStatus(str, Enum):
    SUPPORTED = "SUPPORTED"
    PARTIAL = "PARTIAL"
    INSUFFICIENT = "INSUFFICIENT"
    CONFLICTING = "CONFLICTING"


# ---------------------------------------------
# Source provenance
# ---------------------------------------------

class SourceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_kind: Literal[
        "brochure",
        "service_report",
        "flotation",
    ]

    document_id: str = Field(min_length=1)

    page_number: int | None = Field(
        default=None,
        ge=1,
    )

    location: str | None = None


# ---------------------------------------------
# Product evidence
# ---------------------------------------------

class ProductEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_name: str = Field(min_length=1)
    chunk_id: str = Field(min_length=1)
    excerpt: str = Field(min_length=1)

    source: SourceRef

    quality_flags: list[str] = Field(
        default_factory=list
    )

    @model_validator(mode="after")
    def validate_source(self):
        if (
            self.source.source_kind != "brochure"
            or self.source.page_number is None
        ):
            raise ValueError(
                "Product evidence requires a "
                "brochure source and page number"
            )

        return self


# ---------------------------------------------
# Service cost item
# ---------------------------------------------

class CostItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: Literal[
        "labor",
        "travel",
        "parts",
        "consumables",
        "tax",
        "other",
    ]

    description: str = Field(min_length=1)

    quantity: Decimal | None = Field(
        default=None,
        gt=0,
    )

    unit: str | None = None

    unit_rate: Decimal | None = Field(
        default=None,
        ge=0,
    )

    currency: str | None = None

    amount_reported: Decimal | None = Field(
        default=None,
        ge=0,
    )

    source: SourceRef

    quality_flags: list[str] = Field(
        default_factory=list
    )

    @field_validator("currency")
    @classmethod
    def check_currency(
        cls,
        value: str | None,
    ) -> str | None:

        if (
            value is not None
            and re.fullmatch(r"[A-Z]{3}", value) is None
        ):
            raise ValueError(
                "Currency must be a three-letter "
                "uppercase code, e.g. EUR"
            )

        return value

    @model_validator(mode="after")
    def validate_source(self):

        if self.source.source_kind != "service_report":
            raise ValueError(
                "Cost evidence must reference "
                "a service report"
            )

        return self

    def derived_amount(self) -> Decimal | None:
        """
        Compute from known quantity and rate.
        Never substitute zero for missing data.
        """

        if (
            self.quantity is None
            or self.unit_rate is None
            or self.currency is None
        ):
            return None

        return self.quantity * self.unit_rate


# ---------------------------------------------
# Historical service report
# ---------------------------------------------

class ServiceReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_id: str = Field(
        pattern=r"^FSR-\d{4}$"
    )

    source: SourceRef

    visit_date: date | None = None

    country: str | None = None
    site: str | None = None
    equipment_model: str | None = None

    tasks: list[str] = Field(
        default_factory=list
    )

    labor_hours: Decimal | None = Field(
        default=None,
        ge=0,
    )

    travel_hours: Decimal | None = Field(
        default=None,
        ge=0,
    )

    cost_items: list[CostItem] = Field(
        default_factory=list
    )

    reported_total: Decimal | None = Field(
        default=None,
        ge=0,
    )

    total_currency: str | None = None

    quality_flags: list[str] = Field(
        default_factory=list
    )

    @field_validator("total_currency")
    @classmethod
    def check_currency(
        cls,
        value: str | None,
    ) -> str | None:

        if (
            value is not None
            and re.fullmatch(r"[A-Z]{3}", value) is None
        ):
            raise ValueError(
                "Currency must be a three-letter "
                "uppercase code"
            )

        return value

    @model_validator(mode="after")
    def validate_source(self):

        if self.source.source_kind != "service_report":
            raise ValueError(
                "A service report requires a "
                "service_report source"
            )

        if self.source.document_id != self.report_id:
            raise ValueError(
                "Report ID must agree with its "
                "source document ID"
            )

        return self


# ---------------------------------------------
# Optional flotation statistic
# ---------------------------------------------

class FlotationStatistic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric: str = Field(min_length=1)
    value: Decimal

    sample_size: int = Field(gt=0)

    unit: str | None = None

    source: SourceRef

    @model_validator(mode="after")
    def validate_source(self):

        if self.source.source_kind != "flotation":
            raise ValueError(
                "A flotation statistic requires "
                "a flotation source"
            )

        return self


# ---------------------------------------------
# Final agent response
# ---------------------------------------------

class AgentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=1)

    routes: list[
        Literal[
            "product",
            "service_cost",
            "flotation",
        ]
    ] = Field(default_factory=list)

    status: EvidenceStatus

    sources: list[SourceRef] = Field(
        default_factory=list
    )

    warnings: list[str] = Field(
        default_factory=list
    )

    clarification_question: str | None = None

    @model_validator(mode="after")
    def validate_claim_sources(self):

        if (
            self.status == EvidenceStatus.SUPPORTED
            and self.routes
            and not self.sources
        ):
            raise ValueError(
                "A fully supported domain answer "
                "must cite a source"
            )

        return self