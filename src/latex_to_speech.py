"""
latex_to_speech.py — Convert LaTeX math into natural spoken English.

Uses a combination of:
  1. A lookup table for Greek letters and common operators.
  2. Regex-based pattern matching for structural constructs (fractions,
     superscripts, subscripts, sums, integrals, etc.).
  3. Recursive descent for nested expressions.

This module runs *before* dialogue generation so the LLM receives clean,
speakable text with no raw LaTeX.
"""

from __future__ import annotations

import re
from typing import Optional


# ─────────────────────────────────────────────
# Greek-letter & symbol lookup
# ─────────────────────────────────────────────

GREEK_LETTERS: dict[str, str] = {
    "alpha": "alpha", "beta": "beta", "gamma": "gamma", "delta": "delta",
    "epsilon": "epsilon", "zeta": "zeta", "eta": "eta", "theta": "theta",
    "iota": "iota", "kappa": "kappa", "lambda": "lambda", "mu": "mu",
    "nu": "nu", "xi": "xi", "pi": "pi", "rho": "rho",
    "sigma": "sigma", "tau": "tau", "upsilon": "upsilon", "phi": "phi",
    "chi": "chi", "psi": "psi", "omega": "omega",
    # Uppercase variants
    "Alpha": "Alpha", "Beta": "Beta", "Gamma": "Gamma", "Delta": "Delta",
    "Epsilon": "Epsilon", "Zeta": "Zeta", "Eta": "Eta", "Theta": "Theta",
    "Lambda": "Lambda", "Xi": "Xi", "Pi": "Pi", "Sigma": "Sigma",
    "Phi": "Phi", "Psi": "Psi", "Omega": "Omega",
    # Variant forms
    "varepsilon": "epsilon", "varphi": "phi", "vartheta": "theta",
}

OPERATORS: dict[str, str] = {
    "cdot": "times", "times": "times", "div": "divided by",
    "pm": "plus or minus", "mp": "minus or plus",
    "leq": "less than or equal to", "geq": "greater than or equal to",
    "neq": "not equal to", "approx": "approximately",
    "equiv": "is equivalent to", "propto": "is proportional to",
    "infty": "infinity", "partial": "partial",
    "nabla": "nabla", "forall": "for all", "exists": "there exists",
    "in": "in", "notin": "not in", "subset": "subset of",
    "supset": "superset of", "cup": "union", "cap": "intersection",
    "to": "to", "rightarrow": "arrow", "Rightarrow": "implies",
    "leftarrow": "left arrow", "leftrightarrow": "if and only if",
    "ldots": "and so on", "cdots": "and so on", "dots": "and so on",
    "log": "log", "ln": "natural log of", "exp": "e to the power of",
    "sin": "sine", "cos": "cosine", "tan": "tangent",
    "max": "max", "min": "min", "arg": "arg",
    "lim": "the limit of",
    "det": "determinant of", "mod": "mod",
}

ACCENTS: dict[str, str] = {
    "hat": "hat", "bar": "bar", "tilde": "tilde",
    "vec": "vector", "dot": "dot", "ddot": "double dot",
    "overline": "bar", "underline": "underline",
}


# ─────────────────────────────────────────────
# Brace-matching helper
# ─────────────────────────────────────────────

def _extract_braced(text: str, start: int) -> tuple[str, int]:
    """
    Starting at *start* (which should point at '{'), return the content
    inside the matching braces and the index just past the closing '}'.
    Handles nested braces.
    """
    if start >= len(text) or text[start] != "{":
        # No brace — grab a single token (letter / digit)
        if start < len(text):
            return text[start], start + 1
        return "", start

    depth = 0
    i = start
    while i < len(text):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1 : i], i + 1
        i += 1
    # Unmatched – return everything after opening brace
    return text[start + 1 :], len(text)


def _next_arg(text: str, pos: int) -> tuple[str, int]:
    """Skip optional whitespace, then extract the next braced group or single char."""
    while pos < len(text) and text[pos] == " ":
        pos += 1
    if pos >= len(text):
        return "", pos
    return _extract_braced(text, pos)


# ─────────────────────────────────────────────
# Core recursive converter
# ─────────────────────────────────────────────

def _convert_token_stream(latex: str) -> str:
    """
    Walk through *latex* character by character, recognising commands
    and converting them into spoken English fragments.
    """
    result: list[str] = []
    i = 0
    n = len(latex)

    while i < n:
        ch = latex[i]

        # ── LaTeX command (\something) ─────────────────────────
        if ch == "\\":
            # Collect command name
            j = i + 1
            while j < n and latex[j].isalpha():
                j += 1
            cmd = latex[i + 1 : j]
            i = j  # advance past command name

            # Greek letter
            if cmd in GREEK_LETTERS:
                result.append(GREEK_LETTERS[cmd])
                continue

            # Operator / symbol
            if cmd in OPERATORS:
                result.append(OPERATORS[cmd])
                continue

            # Accent / decoration
            if cmd in ACCENTS:
                arg, i = _next_arg(latex, i)
                inner = _convert_token_stream(arg)
                result.append(f"{inner} {ACCENTS[cmd]}")
                continue

            # Fraction  \frac{a}{b}
            if cmd == "frac":
                num, i = _next_arg(latex, i)
                den, i = _next_arg(latex, i)
                num_spoken = _convert_token_stream(num)
                den_spoken = _convert_token_stream(den)
                result.append(f"{num_spoken} divided by {den_spoken}")
                continue

            # Square root  \sqrt{x}  or  \sqrt[n]{x}
            if cmd == "sqrt":
                # Optional arg [n]
                degree = ""
                if i < n and latex[i] == "[":
                    end_bracket = latex.index("]", i)
                    degree = latex[i + 1 : end_bracket]
                    i = end_bracket + 1
                arg, i = _next_arg(latex, i)
                inner = _convert_token_stream(arg)
                if degree:
                    deg_spoken = _convert_token_stream(degree)
                    result.append(f"the {deg_spoken} root of {inner}")
                else:
                    result.append(f"the square root of {inner}")
                continue

            # Sum / Product with limits
            if cmd in ("sum", "prod"):
                word = "sum" if cmd == "sum" else "product"
                result.append(f"the {word}")
                continue

            # Integral
            if cmd in ("int", "iint", "iiint", "oint"):
                result.append("the integral")
                continue

            # Text commands  \text{...}, \mathrm{...}, \textbf{...}, etc.
            if cmd in ("text", "mathrm", "textbf", "textit", "mathbf",
                        "mathit", "mathcal", "mathbb", "operatorname"):
                arg, i = _next_arg(latex, i)
                result.append(_convert_token_stream(arg))
                continue

            # \left, \right — skip sizing delimiters
            if cmd in ("left", "right", "big", "Big", "bigg", "Bigg"):
                # skip the following delimiter character
                if i < n and latex[i] in r"()[]{}|.\\/":
                    i += 1
                continue

            # \begin{...} / \end{...} — skip environment markers
            if cmd in ("begin", "end"):
                _, i = _next_arg(latex, i)
                continue

            # Unknown command — just emit name
            result.append(cmd)
            continue

        # ── Superscript ────────────────────────────────────────
        if ch == "^":
            i += 1
            arg, i = _next_arg(latex, i)
            inner = _convert_token_stream(arg)
            # Common cases
            if inner == "2":
                result.append("squared")
            elif inner == "3":
                result.append("cubed")
            elif inner == "T":
                result.append("transpose")
            elif inner == "-1":
                result.append("inverse")
            else:
                result.append(f"to the power of {inner}")
            continue

        # ── Subscript ──────────────────────────────────────────
        if ch == "_":
            i += 1
            arg, i = _next_arg(latex, i)
            inner = _convert_token_stream(arg)
            result.append(f"sub {inner}")
            continue

        # ── Braces (grouping) ──────────────────────────────────
        if ch == "{":
            content, i = _extract_braced(latex, i)
            result.append(_convert_token_stream(content))
            continue

        # ── Skip whitespace / noise characters ─────────────────
        if ch in " \t\n":
            i += 1
            continue
        if ch in "&":
            i += 1
            continue

        # ── Infix operators ────────────────────────────────────
        if ch == "+":
            result.append("plus")
            i += 1
            continue
        if ch == "-":
            result.append("minus")
            i += 1
            continue
        if ch == "=":
            result.append("equals")
            i += 1
            continue
        if ch == "<":
            result.append("less than")
            i += 1
            continue
        if ch == ">":
            result.append("greater than")
            i += 1
            continue
        if ch in "()[]|":
            i += 1
            continue
        if ch == ",":
            result.append(",")
            i += 1
            continue

        # ── Literal character (letter / digit) ─────────────────
        result.append(ch)
        i += 1

    return " ".join(result)


# ─────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────

_PLACEHOLDER_RE = re.compile(r"<<LATEX:(\d+)>>")


def latex_to_spoken(expr: str) -> str:
    """
    Convert a single LaTeX expression into spoken English.

    >>> latex_to_spoken(r"x^2 + y^2 = z^2")
    'x squared plus y squared equals z squared'
    >>> latex_to_spoken(r"\\frac{a}{b}")
    'a divided by b'
    """
    return _convert_token_stream(expr).strip()


def replace_latex_placeholders(
    text: str,
    expressions: list[str],
) -> str:
    """
    Replace every ``<<LATEX:n>>`` placeholder in *text* with the
    spoken-English version of ``expressions[n]``.
    """
    def _repl(m: re.Match) -> str:
        idx = int(m.group(1))
        if idx < len(expressions):
            return latex_to_spoken(expressions[idx])
        return ""

    return _PLACEHOLDER_RE.sub(_repl, text)
