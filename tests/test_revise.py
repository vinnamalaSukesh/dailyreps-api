from app.logic.revise import INTERVALS, apply_review, is_due, start


def test_start_is_due_tomorrow():
    rev = start("2026-11-26")
    assert rev == {"step": 0, "nextAt": "2026-11-27", "correct": 0, "wrong": 0, "lastAt": None}


def test_correct_climbs_the_ladder():
    rev = start("2026-11-26")
    days = []
    for _ in range(len(INTERVALS) + 1):
        rev = apply_review(rev, True, "2026-12-01")
        days.append(INTERVALS[rev["step"]])
    assert days == [3, 7, 14, 30, 60, 60, 60]  # tops out at 60 and keeps repeating
    assert rev["correct"] == 7 and rev["wrong"] == 0 and rev["lastAt"] == "2026-12-01"


def test_wrong_resets_to_tomorrow():
    rev = {"step": 4, "nextAt": "2026-11-26", "correct": 4, "wrong": 0, "lastAt": "2026-10-27"}
    out = apply_review(rev, False, "2026-11-26")
    assert out["step"] == 0 and out["nextAt"] == "2026-11-27" and out["wrong"] == 1 and out["correct"] == 4


def test_is_due():
    rev = start("2026-11-26")
    assert not is_due(rev, "2026-11-26")
    assert is_due(rev, "2026-11-27") and is_due(rev, "2026-12-05")
    assert not is_due(None, "2026-12-05")
