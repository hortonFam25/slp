"""`get_available_time_slots`, which used to raise on every single call.

The slot loop stepped the clock with `datetime.replace(minute=minute + n)`.
That works right up to :55 and then raises `ValueError: minute must be in
0..59` -- and since the slot END was computed the same way, a 30-minute
duration blew up at 08:30 on the very first day the endpoint was used. The
route on top of it, `GET /api/scheduling/students/{id}/available-slots`,
returned a 500 for every request that ever reached it.

These tests pin the arithmetic (`timedelta`, which carries into the hour), the
window boundary (a slot is offered only if the whole appointment fits before
`end_hour`), and the conflict rule -- including its two exact-touch edges,
where a slot that ends precisely when an appointment starts is still free.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest


TARGET_DATE = date(2026, 9, 14)


@pytest.fixture(scope="module")
def db(client):
    """A session against the suite's throwaway sqlite file.

    Depends on ``client`` only for its side effect: the app's startup handler is
    what runs ``create_all``.
    """
    from app.db.database import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="module")
def student(db):
    from app.models.student import Student

    row = Student(
        student_alias="pending",
        first="Slotty",
        last="Mcslotface",
        grade_level="2",
        enrollment_status="Active",
    )
    db.add(row)
    db.flush()
    row.student_alias = f"student_{row.id}"
    db.commit()
    return row.id


@pytest.fixture
def repo(db):
    from app.repositories.appointment_repository import AppointmentRepository

    return AppointmentRepository(db)


def _appointment(db, student_id, start: datetime, minutes: int, status: str = "scheduled"):
    from app.models.appointment import Appointment

    row = Appointment(
        student_id=student_id,
        start_datetime=start,
        end_datetime=start + timedelta(minutes=minutes),
        appointment_type="individual",
        status=status,
    )
    db.add(row)
    db.commit()
    return row


@pytest.fixture(autouse=True)
def _no_appointments(db, student):
    """Every test starts from an empty calendar and leaves one behind."""
    from app.models.appointment import Appointment

    db.query(Appointment).filter(Appointment.student_id == student).delete(
        synchronize_session=False
    )
    db.commit()
    yield
    db.query(Appointment).filter(Appointment.student_id == student).delete(
        synchronize_session=False
    )
    db.commit()


def _at(hour: int, minute: int = 0) -> datetime:
    return datetime.combine(TARGET_DATE, datetime.min.time()) + timedelta(
        hours=hour, minutes=minute
    )


# ---------------------------------------------------------------------------
# the arithmetic
# ---------------------------------------------------------------------------
def test_an_empty_day_yields_every_five_minute_start_that_fits(repo, student):
    """The regression itself: this call used to raise before returning a thing."""
    slots = repo.get_available_time_slots(
        student_id=student, target_date=TARGET_DATE, duration_minutes=30,
        start_hour=8, end_hour=17,
    )

    assert slots[0] == _at(8, 0)
    # 8:00 to 16:30 inclusive, every five minutes.
    assert len(slots) == ((16 * 60 + 30) - (8 * 60)) // 5 + 1
    assert slots == sorted(slots)
    assert all(later - earlier == timedelta(minutes=5)
               for earlier, later in zip(slots, slots[1:]))


@pytest.mark.parametrize("duration_minutes", [15, 30, 45, 60, 90])
def test_slot_starts_past_the_fifty_ninth_minute_do_not_raise(repo, student, duration_minutes):
    """The starts where `replace(minute=...)` overflowed, asserted present.

    08:45 + 30 is minute 75; 08:35 + 45 is minute 80; 08:30 + 90 is minute 120.
    Each of those is a `ValueError` under the old code and an ordinary time
    under `timedelta`.
    """
    slots = repo.get_available_time_slots(
        student_id=student, target_date=TARGET_DATE,
        duration_minutes=duration_minutes, start_hour=8, end_hour=17,
    )

    for minute in (30, 35, 45, 55):
        assert _at(8, minute) in slots, minute
    # And the carry actually lands in the next hour rather than wrapping.
    assert _at(9, 0) in slots


def test_a_window_crossing_midday_is_walked_whole(repo, student):
    """No gap where an hour rolls over: 11:55 and 12:00 are both offered."""
    slots = repo.get_available_time_slots(
        student_id=student, target_date=TARGET_DATE, duration_minutes=30,
        start_hour=11, end_hour=13,
    )

    assert _at(11, 55) in slots
    assert _at(12, 0) in slots
    assert all(slot.date() == TARGET_DATE for slot in slots)


# ---------------------------------------------------------------------------
# the window boundary
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "duration_minutes, last_start",
    [(15, (16, 45)), (30, (16, 30)), (45, (16, 15)), (60, (16, 0))],
)
def test_the_last_slot_is_the_last_one_that_fits(repo, student, duration_minutes, last_start):
    """A slot that would run past `end_hour` is not an available slot.

    An 8-17 day means the therapist is gone at 17:00. Offering a 16:45 start for
    a 30-minute appointment books fifteen minutes of a day that does not exist.
    """
    slots = repo.get_available_time_slots(
        student_id=student, target_date=TARGET_DATE,
        duration_minutes=duration_minutes, start_hour=8, end_hour=17,
    )

    assert slots[-1] == _at(*last_start)
    assert slots[-1] + timedelta(minutes=duration_minutes) == _at(17, 0)


def test_a_duration_longer_than_the_window_yields_nothing(repo, student):
    slots = repo.get_available_time_slots(
        student_id=student, target_date=TARGET_DATE, duration_minutes=120,
        start_hour=8, end_hour=9,
    )
    assert slots == []


def test_a_zero_or_negative_duration_yields_nothing_rather_than_looping(repo, student):
    """Guard on the step, not on the caller: a 0-minute slot is not a slot."""
    for duration in (0, -30):
        assert repo.get_available_time_slots(
            student_id=student, target_date=TARGET_DATE,
            duration_minutes=duration, start_hour=8, end_hour=17,
        ) == []


# ---------------------------------------------------------------------------
# conflicts
# ---------------------------------------------------------------------------
def test_an_appointment_removes_exactly_the_slots_that_overlap_it(db, repo, student):
    _appointment(db, student, _at(9, 0), 30)

    slots = repo.get_available_time_slots(
        student_id=student, target_date=TARGET_DATE, duration_minutes=30,
        start_hour=8, end_hour=17,
    )

    # Every start strictly between 08:30 and 09:30 overlaps the 9:00-9:30 booking.
    for minute in range(35, 60, 5):
        assert _at(8, minute) not in slots, minute
    for minute in range(0, 30, 5):
        assert _at(9, minute) not in slots, minute

    # The two exact-touch edges stay available: back-to-back is not a conflict.
    assert _at(8, 30) in slots
    assert _at(9, 30) in slots


def test_a_cancelled_appointment_does_not_hold_its_slot(db, repo, student):
    """Only `scheduled` and `in_progress` occupy time -- the pre-existing rule."""
    _appointment(db, student, _at(10, 0), 30, status="cancelled")

    slots = repo.get_available_time_slots(
        student_id=student, target_date=TARGET_DATE, duration_minutes=30,
        start_hour=10, end_hour=11,
    )
    assert _at(10, 0) in slots


def test_an_archived_appointment_does_not_hold_its_slot(db, repo, student):
    """Archiving must not be worse than deleting -- see the class docstring."""
    from app.models.user import User
    from app.services import archive as archive_service

    user = User(
        external_auth_id="pytest-available-slots",
        email="slots@example.invalid",
        display_name="Slot Tester",
        role="therapist",
        is_active=True,
    )
    db.add(user)
    db.flush()
    row = _appointment(db, student, _at(14, 0), 30)

    slots = repo.get_available_time_slots(
        student_id=student, target_date=TARGET_DATE, duration_minutes=30,
        start_hour=14, end_hour=15,
    )
    assert _at(14, 0) not in slots

    archive_service.archive(
        db, user_id=user.id, entity_type="appointment", entity_id=row.id
    )
    db.expire_all()

    slots = repo.get_available_time_slots(
        student_id=student, target_date=TARGET_DATE, duration_minutes=30,
        start_hour=14, end_hour=15,
    )
    assert _at(14, 0) in slots


def test_another_students_appointment_is_not_this_students_conflict(db, repo, student):
    from app.models.student import Student

    # Names that appear nowhere in ordinary English: the MCP PII sanitizer
    # rewrites every student name it finds in every string the suite produces,
    # so a test student called "Other Student" silently corrupts the assertions
    # in test_mcp_pii.py and test_blind_import.py.
    other = Student(
        student_alias="pending",
        first="Otterly",
        last="Elsewhen",
        grade_level="2",
        enrollment_status="Active",
    )
    db.add(other)
    db.flush()
    other.student_alias = f"student_{other.id}"
    db.commit()
    _appointment(db, other.id, _at(11, 0), 30)

    slots = repo.get_available_time_slots(
        student_id=student, target_date=TARGET_DATE, duration_minutes=30,
        start_hour=11, end_hour=12,
    )
    assert _at(11, 0) in slots


def test_an_appointment_on_another_day_is_not_a_conflict(db, repo, student):
    from app.models.appointment import Appointment

    row = Appointment(
        student_id=student,
        start_datetime=datetime.combine(TARGET_DATE, datetime.min.time())
        + timedelta(days=1, hours=11),
        end_datetime=datetime.combine(TARGET_DATE, datetime.min.time())
        + timedelta(days=1, hours=11, minutes=30),
        appointment_type="individual",
        status="scheduled",
    )
    db.add(row)
    db.commit()

    slots = repo.get_available_time_slots(
        student_id=student, target_date=TARGET_DATE, duration_minutes=30,
        start_hour=11, end_hour=12,
    )
    assert _at(11, 0) in slots


# ---------------------------------------------------------------------------
# the route
# ---------------------------------------------------------------------------
def test_the_route_returns_slots_instead_of_a_five_hundred(client, db, student):
    """`GET /api/scheduling/students/{id}/available-slots`, end to end."""
    _appointment(db, student, _at(9, 0), 30)

    response = client.get(
        f"/api/scheduling/students/{student}/available-slots",
        params={
            "target_date": TARGET_DATE.isoformat(),
            "duration_minutes": 30,
            "start_hour": 8,
            "end_hour": 17,
        },
    )

    assert response.status_code == 200, response.text
    slots = [datetime.fromisoformat(value) for value in response.json()["available_slots"]]
    assert slots[0] == _at(8, 0)
    assert slots[-1] == _at(16, 30)
    assert _at(9, 0) not in slots
    assert _at(8, 30) in slots


def test_the_route_defaults_match_the_repository_defaults(client, student):
    response = client.get(
        f"/api/scheduling/students/{student}/available-slots",
        params={"target_date": TARGET_DATE.isoformat()},
    )
    assert response.status_code == 200, response.text
    slots = response.json()["available_slots"]
    assert datetime.fromisoformat(slots[0]) == _at(8, 0)
    assert datetime.fromisoformat(slots[-1]) == _at(16, 30)
