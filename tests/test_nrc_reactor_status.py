from datetime import datetime, timezone

import pytest

from market_intelligence.connectors.nrc_reactor_status import (
    answer_to_retrieved_record,
    NrcReactorStatusConnector,
    parse_nrc_reactor_status_html,
    parse_nrc_reactor_status_text,
)
from market_intelligence.retrieval.exceptions import (
    SourceResponseError,
)


TITLE = (
    "Power Reactor Status Report "
    "for August 03, 2026"
)

URL = (
    "https://www.nrc.gov/reading-rm/"
    "doc-collections/event-status/"
    "reactor-status/ps"
)


HTML = """
<html>
<head>
<title>Power Reactor Status Report for August 03, 2026</title>
</head>
<body>
<h3>Region 4</h3>
<table>
<tr><th>Unit</th><th>Power</th></tr>
<tr><td>Diablo Canyon 1</td><td>100</td></tr>
<tr><td>Diablo Canyon 2</td><td>100</td></tr>
<tr><td>Palo Verde 1</td><td>95</td></tr>
</table>
</body>
</html>
"""


TEXT = """
Region 4
Unit | Power
Diablo Canyon 1 | 100
Diablo Canyon 2 | 100
Palo Verde 1 | 95
"""


def test_html_parser_extracts_units():
    report = parse_nrc_reactor_status_html(
        HTML,
        source_title=TITLE,
        source_url=URL,
    )

    assert report.report_date.isoformat() == (
        "2026-08-03"
    )
    assert len(report.units) == 3
    assert report.units[0].unit_name == (
        "Diablo Canyon 1"
    )
    assert report.units[0].region == 4


def test_text_parser_extracts_units():
    report = parse_nrc_reactor_status_text(
        TEXT,
        source_title=TITLE,
        source_url=URL,
    )

    assert len(report.units) == 3
    assert report.units[2].power_percent == 95


def test_diablo_canyon_full_capacity_answer():
    report = parse_nrc_reactor_status_text(
        TEXT,
        source_title=TITLE,
        source_url=URL,
    )

    connector = NrcReactorStatusConnector()

    answer = connector.answer_plant_status(
        report=report,
        plant_query="Diablo Canyon",
        question=(
            "Is Diablo Canyon running "
            "at full capacity?"
        ),
    )

    assert "Yes." in answer.direct_answer
    assert len(answer.units) == 2
    assert all(
        unit.full_capacity
        for unit in answer.units
    )
    assert "Diablo Canyon 1: 100%" in (
        answer.simple_explanation
    )


def test_specific_unit_query():
    report = parse_nrc_reactor_status_text(
        TEXT,
        source_title=TITLE,
        source_url=URL,
    )

    connector = NrcReactorStatusConnector()

    answer = connector.answer_plant_status(
        report=report,
        plant_query="Diablo Canyon 2",
        question=(
            "What percentage is Diablo "
            "Canyon Unit 2 operating at?"
        ),
    )

    assert len(answer.units) == 1
    assert answer.units[0].power_percent == 100


def test_unknown_plant_is_rejected():
    report = parse_nrc_reactor_status_text(
        TEXT,
        source_title=TITLE,
        source_url=URL,
    )

    connector = NrcReactorStatusConnector()

    with pytest.raises(
        SourceResponseError,
        match="No NRC",
    ):
        connector.answer_plant_status(
            report=report,
            plant_query="Unknown Plant",
            question="Is it online?",
        )


def test_answer_converts_to_primary_record():
    report = parse_nrc_reactor_status_text(
        TEXT,
        source_title=TITLE,
        source_url=URL,
    )

    connector = NrcReactorStatusConnector()

    answer = connector.answer_plant_status(
        report=report,
        plant_query="Diablo Canyon",
        question=(
            "Is Diablo Canyon running "
            "at full capacity?"
        ),
    )

    record = answer_to_retrieved_record(
        answer
    )

    assert record.is_primary is True
    assert record.provider_id == (
        "nrc_reactor_status"
    )
    assert record.payload["unit"] == (
        "percent of rated power"
    )
    assert record.metadata["has_unit"] is True


def test_empty_status_page_is_rejected():
    with pytest.raises(
        SourceResponseError,
        match="usable reactor",
    ):
        parse_nrc_reactor_status_text(
            "No reactor table available",
            source_title=TITLE,
            source_url=URL,
        )


def test_unit_number_is_never_treated_as_power():
    with pytest.raises(
        SourceResponseError,
        match="usable reactor",
    ):
        parse_nrc_reactor_status_text(
            """
            Region 4
            Diablo Canyon 1
            Diablo Canyon 2
            """,
            source_title=TITLE,
            source_url=URL,
        )
