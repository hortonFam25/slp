"""`GET /api/goals-csv/template`, which used to be a guaranteed 500.

`generate_goals_csv_template` kept two hand-maintained literals -- a header
list and a sample-row dict -- and they had drifted apart in three places:
`prog Date1 ` carried a trailing space the sample row did not, `progdate2` was
spelled differently in the two lists, and `Prog Comments 2` through
`Prog Comments 5` existed only in the sample row. `csv.DictWriter` raises
`ValueError: dict contains fields not in fieldnames` on the first of those, so
the route returned a 500 for every request that ever reached it.

The header row is derived from one list now and the sample row is derived from
the header row, so the two cannot disagree. These tests pin that, and pin the
thing that actually matters to a therapist: a template downloaded from the app
goes back into the app's own importer without a single column being renamed.
"""

from __future__ import annotations

import csv
from io import StringIO

import pytest


def _template() -> str:
    from app.schemas.goals_import import generate_goals_csv_template

    return generate_goals_csv_template()


# ---------------------------------------------------------------------------
# the invariant that broke
# ---------------------------------------------------------------------------
def test_the_header_row_and_the_sample_row_have_the_same_columns():
    """The regression, stated as the thing DictWriter was asserting for us."""
    reader = csv.DictReader(StringIO(_template()))
    rows = list(reader)

    assert len(rows) == 1, "the template carries exactly one worked example"
    assert list(rows[0].keys()) == reader.fieldnames
    assert None not in rows[0], "a sample value with no column of its own"


def test_the_columns_are_the_ones_the_importer_reads():
    """Spelled out, so a rename has to be a deliberate edit in two places."""
    from app.schemas.goals_import import goals_csv_template_columns

    reader = csv.DictReader(StringIO(_template()))
    assert reader.fieldnames == goals_csv_template_columns()

    expected = ["ID", "Goal", "Responsible Staff"]
    for slot in range(1, 6):
        expected += [
            f"Objective{slot}",
            f"Schedule{slot}",
            f"Prog Comments {slot}",
            f"prog Date{slot}",
        ]
    assert reader.fieldnames == expected


def test_no_column_name_carries_stray_whitespace():
    """`prog Date1 ` was one of the three drifts; it is not coming back."""
    reader = csv.DictReader(StringIO(_template()))
    for name in reader.fieldnames:
        assert name == name.strip(), repr(name)
    assert len(set(reader.fieldnames)) == len(reader.fieldnames), "duplicate column"


def test_all_five_objective_slots_have_a_progress_comments_column():
    """The drift that silently cost data rather than raising: slots 2-5."""
    reader = csv.DictReader(StringIO(_template()))
    for slot in range(1, 6):
        assert f"Prog Comments {slot}" in reader.fieldnames, slot


def test_an_example_row_key_with_no_column_is_refused_loudly():
    """The guard, exercised: a bad edit fails with a message naming the column."""
    from app.schemas import goals_import

    original = goals_import._TEMPLATE_EXAMPLE_ROW
    goals_import._TEMPLATE_EXAMPLE_ROW = dict(original, progdate9="2/24/2025")
    try:
        with pytest.raises(ValueError) as raised:
            goals_import.generate_goals_csv_template()
        assert "progdate9" in str(raised.value)
    finally:
        goals_import._TEMPLATE_EXAMPLE_ROW = original


# ---------------------------------------------------------------------------
# the round trip
# ---------------------------------------------------------------------------
def test_the_template_parses_back_through_the_apps_own_importer():
    """A downloaded template, filled in, must be importable as-is."""
    from app.schemas.goals_import import (
        convert_legacy_csv_to_goal_import,
        parse_goals_csv_content,
    )

    rows = parse_goals_csv_content(_template())
    assert len(rows) == 1

    goal = convert_legacy_csv_to_goal_import(rows[0])
    assert goal.student_uic == "1234567890"
    assert goal.responsible_staff == "Speech Pathologist"
    # Three worked objectives; slots 4 and 5 are blank on purpose and must not
    # arrive as empty objectives.
    assert len(goal.objectives) == 3
    assert all(o.schedule_frequency == "Monthly updates" for o in goal.objectives)
    assert all(o.progress_comments for o in goal.objectives)
    # The date column is found and normalised despite the M/D/YYYY sample.
    assert all(o.progress_date == "2025-02-24" for o in goal.objectives)


def test_the_template_columns_match_what_the_export_writes():
    """Export then edit then re-import: the same column names throughout."""
    import inspect

    from app.routers import goals_import as router_module
    from app.schemas.goals_import import goals_csv_template_columns

    source = inspect.getsource(router_module.export_goals_csv)
    for column in goals_csv_template_columns():
        assert repr(column) in source or f"'{column}'" in source, column


# ---------------------------------------------------------------------------
# the route
# ---------------------------------------------------------------------------
def test_the_route_returns_a_csv_instead_of_a_five_hundred(client):
    response = client.get("/api/goals-csv/template")

    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv")
    assert "goals_objectives_template.csv" in response.headers["content-disposition"]

    reader = csv.DictReader(StringIO(response.text))
    rows = list(reader)
    assert reader.fieldnames == list(rows[0].keys())
    assert rows[0]["ID"] == "1234567890"
