"""Constants for the calculator MCP server.

Everything the evaluator is permitted to do is enumerated here: the operator
aliases applied before parsing, the name and function allowlists, and the
resource caps. Nothing is derived at import time from ``math``'s contents — the
allowlists are written out so that widening the surface is a deliberate edit
that shows up in a diff.

See [SAFE-EVALUATION.md](../../docs/tech/SAFE-EVALUATION.md) for the threat
model these values implement.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Final

# --- Operator aliases -------------------------------------------------------

# Applied as plain string substitution before parsing. `^` is bitwise XOR in
# Python but exponentiation in every calculator UI, and the Unicode forms are
# what a speech-to-text layer produces when a resident says "times" or "minus".
OPERATOR_ALIASES: Final[dict[str, str]] = {
    "^": "**",
    "×": "*",
    "·": "*",
    "÷": "/",
    "−": "-",  # U+2212 MINUS SIGN, not U+002D HYPHEN-MINUS
}

# --- Allowlists -------------------------------------------------------------

ALLOWED_CONSTANTS: Final[dict[str, float]] = {
    "pi": math.pi,
    "e": math.e,
    "tau": math.tau,
}

# `inf` and `nan` are deliberately absent: they are not useful answers to a
# spoken question and they propagate silently through the rest of an expression.
ALLOWED_FUNCTIONS: Final[dict[str, Callable[..., float]]] = {
    # builtins — referenced directly, never resolved through `__builtins__`
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    # roots, powers, logarithms
    "sqrt": math.sqrt,
    "exp": math.exp,
    "log": math.log,
    "log2": math.log2,
    "log10": math.log10,
    # trigonometry
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "atan2": math.atan2,
    "degrees": math.degrees,
    "radians": math.radians,
    "hypot": math.hypot,
    # rounding and integer maths
    "floor": math.floor,
    "ceil": math.ceil,
    "factorial": math.factorial,
    "gcd": math.gcd,
    "lcm": math.lcm,
}

# --- Resource caps ----------------------------------------------------------

# A first gate before parsing, so a pathological input is rejected without
# building an AST for it.
MAX_EXPRESSION_LENGTH: Final = 500

# Bounds recursion in the evaluator's walk. Deep enough that no expression a
# person would type reaches it; `((((1))))` is only 1 level, since redundant
# parentheses produce no nodes.
MAX_AST_DEPTH: Final = 32

# Caps the size of any integer result. 4300 is CPython's default int-to-string
# conversion limit, so a larger result could not be rendered anyway — making
# this the natural place to draw the line rather than an arbitrary one.
MAX_RESULT_DIGITS: Final = 4300

# 1000! has 2568 digits and computes in well under a millisecond; 2000! has
# 5736 and so exceeds MAX_RESULT_DIGITS regardless.
MAX_FACTORIAL_ARG: Final = 1000

# Significant digits kept when rendering a float. IEEE-754 representation noise
# appears around the 16th digit, so collapsing at 12 removes it while keeping
# far more precision than a calculator result is ever used at.
RESULT_PRECISION: Final = 12
