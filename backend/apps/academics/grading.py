"""Grade bands used for results and certificates."""

BANDS = [(80, "A"), (70, "B"), (60, "C"), (50, "D"), (0, "F")]


def grade_for(score: int) -> str:
    return next(g for floor, g in BANDS if score >= floor)


def remark_for(score: int) -> str:
    if score >= 85:
        return "Excellent work"
    if score >= 70:
        return "Very good"
    if score >= 60:
        return "Good — keep practising"
    return "Fair"
