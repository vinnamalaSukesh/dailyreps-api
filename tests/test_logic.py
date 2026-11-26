from bson import ObjectId

from app.logic.revisit import apply_result, candidates, fill_with_top, score
from app.logic.streaks import allowed_excuses, best_streak, current_streak, excuse_left


def q(**kw):
    base = {"_id": ObjectId(), "level": "medium", "pattern": "two pointers",
            "step": 0, "failCount": 0, "mastered": False, "nextRevisitAt": "2026-11-20"}
    return base | kw


def test_first_attempt_starts_at_one_day():
    out = apply_result(q(step=3), "solved", "2026-11-20", is_first=True)
    assert out["step"] == 0 and out["nextRevisitAt"] == "2026-11-21"


def test_ladder_moves():
    assert apply_result(q(step=1), "solved", "2026-11-20", False)["nextRevisitAt"] == "2026-11-27"
    assert apply_result(q(step=2), "solved_with_hint", "2026-11-20", False)["step"] == 2
    failed = apply_result(q(step=3, failCount=1), "failed", "2026-11-20", False)
    assert failed["step"] == 0 and failed["failCount"] == 2


def test_mastered_after_30_day_step():
    out = apply_result(q(step=4), "solved", "2026-11-20", False)
    assert out["mastered"] and out["nextRevisitAt"] is None


def test_score_formula():
    assert score(q(nextRevisitAt="2026-11-17", failCount=2, level="hard"), "2026-11-20") == 3 * 2 + 6 + 2


def test_candidates_skip_recent_pattern_and_future():
    a = q(pattern="dp", nextRevisitAt="2026-11-18")
    b = q(pattern="graphs", nextRevisitAt="2026-11-21")  # nearly due
    c = q(pattern="trees", nextRevisitAt="2026-11-25")  # not due
    out = candidates([a, b, c], {"dp"}, "2026-11-20", set())
    assert [x["pattern"] for x in out] == ["graphs"]


def test_candidates_relax_cooldown_when_empty():
    a = q(pattern="dp", nextRevisitAt="2026-11-18")
    assert candidates([a], {"dp"}, "2026-11-20", set()) == [a]


def test_fill_with_top_rejects_invalid_ai_pick():
    a, b = q(), q()
    assert fill_with_top(["bogus"], [a, b], 1) == [str(a["_id"])]
    assert fill_with_top([str(b["_id"])], [a, b], 2) == [str(b["_id"]), str(a["_id"])]


def test_streaks():
    days = ["2026-11-17", "2026-11-18", "2026-11-19"]
    assert current_streak(days, "2026-11-20") == 3  # today not done yet
    assert current_streak(days + ["2026-11-20"], "2026-11-20") == 4
    assert current_streak(days, "2026-11-21") == 0
    assert best_streak(days + ["2026-11-01"]) == 3


def test_excused_day_bridges_but_does_not_count():
    done = ["2026-11-16", "2026-11-17", "2026-11-19"]  # missed Wed 18th
    assert current_streak(done, "2026-11-19") == 1
    assert current_streak(done, "2026-11-19", {"2026-11-18"}) == 3
    assert best_streak(done, {"2026-11-18"}) == 3
    # Excused today keeps the streak alive into tomorrow.
    assert current_streak(done, "2026-11-21", {"2026-11-18", "2026-11-20"}) == 3


def test_excuses_capped_per_week_and_done_days_dont_use_them():
    # Mon 16 .. Sun 22 is one week; Mon 23 starts the next.
    missed = ["2026-11-17", "2026-11-18", "2026-11-23"]
    assert allowed_excuses(missed, []) == {"2026-11-17", "2026-11-23"}
    assert allowed_excuses(missed, ["2026-11-17"]) == {"2026-11-18", "2026-11-23"}
    assert excuse_left(["2026-11-17"], [], "2026-11-19") is False
    assert excuse_left([], [], "2026-11-19") is True
    assert excuse_left(["2026-11-17"], [], "2026-11-23") is True
