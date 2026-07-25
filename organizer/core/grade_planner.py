"""Grade Target Planner -- pure calculation, no paid AI, no model logic
beyond what's already on GradeTarget. Solves for the exam score needed to
reach a target overall percentage, given whatever coursework/test marks
are already known.
"""

from typing import Optional


def required_exam_score(
    coursework_weight: int,
    coursework_score: Optional[int],
    test_weight: int,
    test_score: Optional[int],
    exam_weight: int,
    target_percent: int,
) -> dict:
    """Returns {"required": float|None, "achievable": bool|None,
    "provisional": bool, "message": str}.

    A missing component score is treated as 0 for the arithmetic, but
    `provisional=True` (and the message) says so explicitly rather than
    silently presenting a 0-assumption projection as a real one.
    """
    provisional = coursework_score is None or test_score is None
    contributed = (
        (coursework_weight / 100) * (coursework_score or 0)
        + (test_weight / 100) * (test_score or 0)
    )

    if exam_weight <= 0:
        return {
            "required": None,
            "achievable": None,
            "provisional": provisional,
            "message": (
                "This subject has no exam weight set, so there's nothing to solve for; "
                "your target depends entirely on coursework and tests."
            ),
        }

    required = (target_percent - contributed) / (exam_weight / 100)

    if required <= 0:
        achievable = True
        message = "You've already secured this target from coursework and tests alone."
    elif required <= 100:
        achievable = True
        message = f"You need {required:.0f}% in the exam to reach {target_percent}% overall."
    else:
        achievable = False
        message = (
            f"Even 100% in the exam won't reach {target_percent}% overall "
            "with your current coursework and test marks."
        )

    if provisional:
        message += " This assumes 0 for any component you haven't scored yet."

    return {
        "required": round(required, 1),
        "achievable": achievable,
        "provisional": provisional,
        "message": message,
    }
