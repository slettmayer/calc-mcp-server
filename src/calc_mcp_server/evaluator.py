"""Safe arithmetic evaluation over an AST allowlist.

Two separate problems are solved here, and most calculator servers only solve
the first:

1. **Code execution.** Only the node types handled in ``_evaluate`` are
   reachable. ``Attribute`` is not among them, which is what blocks
   ``(1).__class__.__bases__`` chains, and a ``Call`` is only evaluated when its
   func is a bare ``Name`` in ``ALLOWED_FUNCTIONS``, which is what blocks
   ``__import__('os').system(...)``.
2. **Resource exhaustion.** An allowlist alone still lets ``9**9**9`` occupy the
   process for minutes on unbounded bignum exponentiation. The caps in
   ``const`` bound expression length, nesting depth, exponentiation size,
   factorial argument and final result size.

Integers are never coerced to float, so ``123456789 * 987654321`` returns the
exact ``121932631112635269``. That exactness is the entire reason an agent
should reach for this tool rather than doing the arithmetic itself.

See [SAFE-EVALUATION.md](../../docs/tech/SAFE-EVALUATION.md).
"""

from __future__ import annotations

import ast
import math
import operator

from calc_mcp_server.const import (
    ALLOWED_CONSTANTS,
    ALLOWED_FUNCTIONS,
    MAX_AST_DEPTH,
    MAX_EXPRESSION_LENGTH,
    MAX_FACTORIAL_ARG,
    MAX_RESULT_DIGITS,
    OPERATOR_ALIASES,
    RESULT_PRECISION,
)

Number = int | float

# Converts a bit count to a decimal digit count, for sizing an integer result
# without calling str() on it (which is exactly what the cap exists to avoid).
_LOG10_2 = math.log10(2)


class CalculatorError(Exception):
    """Base class for every expression the calculator refuses to evaluate."""


class ExpressionSyntaxError(CalculatorError):
    """The expression is not parseable as arithmetic."""


class UnsupportedExpressionError(CalculatorError):
    """The expression parses, but uses a construct outside the allowlist."""


class LimitExceededError(CalculatorError):
    """The expression is well-formed but too expensive to evaluate or render."""


class MathError(CalculatorError):
    """The arithmetic itself failed — domain error, division by zero, bad args."""


def _guarded_pow(base: Number, exponent: Number) -> Number:
    """Exponentiate, refusing results too large to compute or render.

    The size is estimated from the operands, before any bignum work happens.
    Capping the exponent alone is not sufficient: ``(10**300)**300`` has an
    exponent of just 300 and a 90,000-digit result.
    """
    if exponent > 0 and abs(base) > 1:
        digits = math.log10(abs(base)) * exponent + 1
        if digits > MAX_RESULT_DIGITS:
            raise LimitExceededError(
                f"exponent too large: the result would have about {digits:.0f} "
                f"digits, over the limit of {MAX_RESULT_DIGITS}"
            )
    return operator.pow(base, exponent)


_BINARY_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: _guarded_pow,
}

_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _evaluate_call(node: ast.Call, depth: int) -> Number:
    """Evaluate an allowlisted function call.

    The func must be a bare ``Name`` that is in the allowlist. Anything else —
    an attribute chain, or a call on the result of another call — is rejected
    before a single argument is evaluated.
    """
    if not isinstance(node.func, ast.Name) or node.func.id not in ALLOWED_FUNCTIONS:
        raise UnsupportedExpressionError("unsupported expression: Call")
    if node.keywords:
        raise UnsupportedExpressionError("keyword arguments are not supported")

    name = node.func.id
    args = [_evaluate(argument, depth + 1) for argument in node.args]

    # math.factorial itself has no cap, and only errors on very large arguments
    # by the accident of CPython's int-to-string limit — long after the CPU time
    # has been spent.
    if name == "factorial" and args and args[0] > MAX_FACTORIAL_ARG:
        raise LimitExceededError(
            f"argument too large: factorial is capped at {MAX_FACTORIAL_ARG}"
        )

    return ALLOWED_FUNCTIONS[name](*args)


def _evaluate(node: ast.AST, depth: int) -> Number:
    """Evaluate one AST node, recursing into its allowed children."""
    if depth > MAX_AST_DEPTH:
        raise LimitExceededError(
            f"expression nests deeper than the limit of {MAX_AST_DEPTH} levels"
        )

    if isinstance(node, ast.Constant):
        # bool is a subclass of int, so `True + 1` would otherwise evaluate to 2.
        if isinstance(node.value, bool) or not isinstance(node.value, int | float):
            raise UnsupportedExpressionError(
                f"unsupported literal: {type(node.value).__name__}"
            )
        return node.value

    if isinstance(node, ast.Name):
        if node.id not in ALLOWED_CONSTANTS:
            raise UnsupportedExpressionError(f"unknown name: {node.id}")
        return ALLOWED_CONSTANTS[node.id]

    if isinstance(node, ast.UnaryOp):
        unary_op = _UNARY_OPS.get(type(node.op))
        if unary_op is None:
            raise UnsupportedExpressionError(
                f"unsupported operator: {type(node.op).__name__}"
            )
        return unary_op(_evaluate(node.operand, depth + 1))

    if isinstance(node, ast.BinOp):
        binary_op = _BINARY_OPS.get(type(node.op))
        if binary_op is None:
            raise UnsupportedExpressionError(
                f"unsupported operator: {type(node.op).__name__}"
            )
        return binary_op(
            _evaluate(node.left, depth + 1), _evaluate(node.right, depth + 1)
        )

    if isinstance(node, ast.Call):
        return _evaluate_call(node, depth)

    raise UnsupportedExpressionError(f"unsupported expression: {type(node).__name__}")


def evaluate(expression: str) -> Number:
    """Evaluate an arithmetic expression, returning an exact int or a float.

    Raises a `CalculatorError` subclass for anything it will not evaluate; it
    never lets an arbitrary exception escape.
    """
    if len(expression) > MAX_EXPRESSION_LENGTH:
        raise LimitExceededError(
            f"expression is longer than the limit of {MAX_EXPRESSION_LENGTH} characters"
        )

    normalized = expression
    for alias, replacement in OPERATOR_ALIASES.items():
        normalized = normalized.replace(alias, replacement)

    if not normalized.strip():
        raise ExpressionSyntaxError("the expression is empty")

    try:
        tree = ast.parse(normalized, mode="eval")
    except SyntaxError as err:
        raise ExpressionSyntaxError(
            f"could not parse the expression: {err.msg}"
        ) from err

    try:
        result = _evaluate(tree.body, depth=0)
    except ZeroDivisionError as err:
        raise MathError("division by zero") from err
    except (ValueError, TypeError) as err:
        raise MathError(str(err)) from err
    except OverflowError as err:
        raise LimitExceededError(f"result too large to represent: {err}") from err
    except RecursionError as err:
        raise LimitExceededError("the expression nests too deeply") from err

    # Python returns a complex number for a negative base raised to a fractional
    # power, e.g. `(-8) ** (1/3)`. That is not an answer this tool should give.
    if isinstance(result, complex):
        raise MathError("the result is a complex number")
    return result


def format_result(value: Number) -> str:
    """Render a result, preserving integer exactness and hiding float noise.

    Integers are rendered in full, so `123456789 * 987654321` reads as exactly
    `121932631112635269` rather than a rounded float.

    Floats are collapsed to `RESULT_PRECISION` significant digits first, which
    removes IEEE-754 representation noise (`0.1 + 0.2` would otherwise render as
    `0.30000000000000004`). The trailing `.0` on a whole float is kept, so `8 / 2`
    reads `4.0` and stays visibly distinct from the exact integer `4`.
    """
    if isinstance(value, int):
        # Sized via bit_length rather than len(str(value)): str() on a large
        # enough int raises, which is the very failure this guard prevents.
        if value.bit_length() * _LOG10_2 > MAX_RESULT_DIGITS:
            raise LimitExceededError(
                f"the result has more than {MAX_RESULT_DIGITS} digits"
            )
        return str(value)

    if math.isnan(value) or math.isinf(value):
        return str(value)

    return str(float(f"{value:.{RESULT_PRECISION}g}"))
