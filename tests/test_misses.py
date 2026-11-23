from app.logic.misses import DEFAULT_REASONS, suggestions


def test_defaults_when_no_history():
    assert suggestions([], "workout") == DEFAULT_REASONS["workout"]
    assert suggestions([], "workout")[0] == "Muscle soreness from yesterday"


def test_own_reasons_first_by_frequency_without_duplicating_defaults():
    past = ["Office party", "Power cut", "Office party", "  ", "muscle soreness from yesterday"]
    out = suggestions(past, "workout")
    assert out[:2] == ["Office party", "Power cut"]
    assert sum(r.casefold() == "muscle soreness from yesterday" for r in out) == 1


def test_own_reasons_capped():
    out = suggestions([f"r{i}" for i in range(10)], "dsa", limit=3)
    assert out[:3] == ["r0", "r1", "r2"] and out[3:] == DEFAULT_REASONS["dsa"]
