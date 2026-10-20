# Metso Evidence Agent

A minimal conversational AI sales-support assistant developed for the
Metso AI Solution Engineer take-home assignment.

## Features

- Product recommendations grounded in supplied Metso brochures
- Historical field-service cost comparisons with traceable references
- Optional descriptive flotation-data analysis
- Autonomous tool selection and conversational follow-ups
- Evidence validation and conservative uncertainty handling
- Command-line interface and automated regression tests

## Architecture

The conversational agent chooses between three local tools:

1. search_product_brochures
2. compare_service_costs
3. analyze_flotation

A response-validation layer checks source references and unsupported
claims before an answer is displayed.

## Requirements

- Python 3.12
- Dependencies declared in pyproject.toml
- An API key for the configured LLM provider
- Authorized local copies of the assignment data

## Installation

Create a virtual environment:

    python -m venv .venv

On Windows, install the project:

    .venv\Scripts\python.exe -m pip install -e .

Install pytest if it is not already available:

    .venv\Scripts\python.exe -m pip install pytest

## Private data

The original employer-provided data is intentionally excluded from
this public repository.

Authorized users should place the source materials under:

    raw/data/brochures/
    raw/data/HistoricalServices/
    raw/data/flotation_process_data_hourly.csv

The first two folders support the mandatory workflows.
The CSV supports the optional flotation workflow.

The repository does not distribute the original brochures,
field-service reports, flotation dataset, private evaluation files,
or API credentials.

## Running the agent

Display the help menu:

    python main.py --help

Check local dependencies and source availability:

    python main.py --check-local

Start an interactive session:

    python main.py --allow-external-evidence --verbose

Type exit to end the conversation.

## Testing

    python -m pytest -q

The development environment passed 154 tests on October 19, 2026.
Some tests require authorized local assignment data and therefore
cannot be expected to pass in a clean clone without that data.

## Safety and limitations

Product capability claims must be supported by supplied brochures.
Service-cost comparisons rely only on historical field-service reports.
Historical amounts are not binding commercial quotations.

Amounts in different currencies are not directly added without
documented conversion information.

Flotation analysis provides historical descriptive statistics, not
contractual acceptance decisions or causal diagnoses.

The response validator is conservative. On some combined-intent
queries, a safe fallback may return only the service-cost evidence
rather than a complete multi-tool synthesis.

The --allow-external-evidence flag explicitly authorizes transmitting
selected private evidence excerpts to the configured API provider.
Use it only when permitted.

## Project scope

This is an engineering take-home prototype, not a production
quotation, equipment-control, or plant-optimization system.
