"""Tests for the safe expression evaluator.

The `ACCEPTANCE_*` tables are the matrix from the handover that motivated this
server: each row is either something the abandoned `mcp-server-calculator` got
right and we must not regress, or something it got wrong and we exist to fix.
"""

from __future__ import annotations

import time

import pytest

from calc_mcp_server.const import MAX_EXPRESSION_LENGTH, MAX_RESULT_DIGITS
from calc_mcp_server.evaluator import (
    ExpressionSyntaxError,
    LimitExceededError,
    MathError,
    UnsupportedExpressionError,
    evaluate,
    format_result,
)

# --- Acceptance matrix: expressions that must evaluate ----------------------

ACCEPTANCE_VALID = [
    # (expression, rendered result)
    ("2 + 3 * (4 - 1) / 2 ** 2", "4.25"),
    ("sqrt(16) + sin(pi/2)", "5.0"),
    # Exact, not the 121932631112635260 that a float64 implementation returns.
    ("123456789 * 987654321", "121932631112635269"),
    ("2^10", "1024"),
    ("8 ÷ 2", "4.0"),
    ("6 × 7", "42"),
    ("10 − 4", "6"),
    ("factorial(20)", "2432902008176640000"),
    ("2 ** 100", "1267650600228229401496703205376"),
    ("-5 + 3", "-2"),
    ("17 // 5", "3"),
    ("17 % 5", "2"),
    ("round(3.14159, 2)", "3.14"),
    ("max(1, 2, 3) + min(4, 5)", "7"),
    ("log10(1000)", "3.0"),
    ("degrees(pi)", "180.0"),
    ("abs(-7)", "7"),
]


@pytest.mark.parametrize(("expression", "expected"), ACCEPTANCE_VALID)
def test_evaluate_valid_expressions(expression: str, expected: str) -> None:
    assert format_result(evaluate(expression)) == expected


def test_evaluate_preserves_integer_exactness() -> None:
    """Integer arithmetic must never be coerced to float."""
    result = evaluate("123456789 * 987654321")
    assert isinstance(result, int)
    assert result == 121932631112635269


# --- Acceptance matrix: expressions that must be rejected -------------------

ACCEPTANCE_REJECTED = [
    # (expression, exception type, fragment of the message)
    ("__import__('os').system('echo pwned')", UnsupportedExpressionError, "Call"),
    ("(1).__class__.__bases__", UnsupportedExpressionError, "Attribute"),
    ("().__class__.__bases__[0]", UnsupportedExpressionError, "Subscript"),
    ("open('/etc/passwd')", UnsupportedExpressionError, "Call"),
    ("9**9**9", LimitExceededError, "exponent too large"),
    ("factorial(200000)", LimitExceededError, "argument too large"),
    ("1/0", MathError, "division by zero"),
    ("x + 1", UnsupportedExpressionError, "unknown name: x"),
    ("'abc'", UnsupportedExpressionError, "unsupported literal: str"),
    ("True + 1", UnsupportedExpressionError, "unsupported literal: bool"),
    ("[1, 2, 3]", UnsupportedExpressionError, "unsupported expression: List"),
    ("1 if 2 else 3", UnsupportedExpressionError, "unsupported expression: IfExp"),
    ("1 < 2", UnsupportedExpressionError, "unsupported expression: Compare"),
    ("lambda: 1", UnsupportedExpressionError, "unsupported expression: Lambda"),
    ("2 & 3", UnsupportedExpressionError, "unsupported operator: BitAnd"),
    ("2 +", ExpressionSyntaxError, "could not parse"),
    ("", ExpressionSyntaxError, "empty"),
    ("   ", ExpressionSyntaxError, "empty"),
]


@pytest.mark.parametrize(("expression", "exception", "fragment"), ACCEPTANCE_REJECTED)
def test_evaluate_rejects(
    expression: str, exception: type[Exception], fragment: str
) -> None:
    with pytest.raises(exception, match=fragment):
        evaluate(expression)


# --- Resource caps ----------------------------------------------------------


def test_exponent_bomb_is_rejected_quickly() -> None:
    """`9**9**9` hung the incumbent for over five seconds. It must not hang here.

    The guard is checked against the operands before any bignum work, so this
    should return in well under a millisecond; the second is pure headroom for
    a loaded CI runner.
    """
    started = time.perf_counter()
    with pytest.raises(LimitExceededError, match="exponent too large"):
        evaluate("9**9**9")
    assert time.perf_counter() - started < 1.0


def test_large_base_with_small_exponent_is_rejected() -> None:
    """Capping the exponent alone would let this through with 90,000 digits."""
    with pytest.raises(LimitExceededError, match="exponent too large"):
        evaluate("(10**300)**300")


def test_pow_within_the_cap_is_allowed() -> None:
    assert evaluate("2 ** 1000") == 2**1000


def test_factorial_within_the_cap_is_allowed() -> None:
    assert evaluate("factorial(1000)") > 0


def test_multiplication_past_the_digit_cap_is_rejected_at_render() -> None:
    """Repeated multiplication can exceed the cap without touching `**`."""
    with pytest.raises(LimitExceededError, match="more than"):
        format_result(evaluate("factorial(1000) * factorial(1000)"))


def test_expression_length_is_capped() -> None:
    with pytest.raises(LimitExceededError, match="longer than"):
        evaluate("1+" * MAX_EXPRESSION_LENGTH + "1")


def test_nesting_depth_is_capped() -> None:
    with pytest.raises(LimitExceededError, match="nests deeper"):
        evaluate("1+" * 40 + "1")


@pytest.mark.parametrize("expression", ["sqrt(-1)", "log(0)", "factorial(2.5)"])
def test_math_domain_failures_become_math_errors(expression: str) -> None:
    """Only the type is asserted: the stdlib reworded these between 3.12 and 3.14."""
    with pytest.raises(MathError):
        evaluate(expression)


def test_negative_base_fractional_power_is_rejected() -> None:
    """Python returns a complex number here; that is not a calculator answer."""
    with pytest.raises(MathError, match="complex"):
        evaluate("(-8) ** (1/3)")


# --- Result rendering -------------------------------------------------------


def test_format_result_hides_float_noise() -> None:
    """IEEE-754 noise appears around the 16th digit; 12 significant digits hide it."""
    assert format_result(evaluate("0.1 + 0.2")) == "0.3"
    assert format_result(evaluate("1.1 * 3")) == "3.3"


def test_format_result_keeps_whole_floats_distinguishable_from_ints() -> None:
    assert format_result(8 / 2) == "4.0"
    assert format_result(4) == "4"


def test_format_result_keeps_genuine_precision() -> None:
    assert format_result(evaluate("1 / 3")) == "0.333333333333"
    assert format_result(evaluate("2 / 7")) == "0.285714285714"


def test_format_result_renders_large_integers_in_full() -> None:
    assert format_result(evaluate("2 ** 200")) == str(2**200)
    assert len(format_result(evaluate("factorial(500)"))) < MAX_RESULT_DIGITS
