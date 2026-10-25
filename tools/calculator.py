"""Simple calculator script.

Supports addition, subtraction, multiplication, and division via a
command-line interface, plus a small REPL for interactive use.
"""

from __future__ import annotations

import sys
from typing import Callable


def add(a: float, b: float) -> float:
    """Return the sum of a and b."""
    return a + b


def subtract(a: float, b: float) -> float:
    """Return a minus b."""
    return a - b


def multiply(a: float, b: float) -> float:
    """Return the product of a and b."""
    return a * b


def divide(a: float, b: float) -> float:
    """Return a divided by b.

    Raises:
        ZeroDivisionError: if b is zero.
    """
    if b == 0:
        raise ZeroDivisionError("Cannot divide by zero.")
    return a / b


_OPERATIONS: dict[str, Callable[[float, float], float]] = {
    "+": add,
    "-": subtract,
    "*": multiply,
    "/": divide,
    "add": add,
    "subtract": subtract,
    "multiply": multiply,
    "divide": divide,
}


def calculate(a: float, op: str, b: float) -> float:
    """Apply operation ``op`` to ``a`` and ``b`` and return the result."""
    if op not in _OPERATIONS:
        raise ValueError(
            f"Unknown operation '{op}'. Use one of: {', '.join(_OPERATIONS)}."
        )
    return _OPERATIONS[op](a, b)


def _prompt(prompt: str) -> str:
    return input(prompt).strip()


def repl() -> None:
    """Run an interactive calculator loop until the user quits."""
    print("Simple Calculator — type 'quit' to exit.")
    print("Examples: 2 + 3   |   10 / 4   |   quit")
    while True:
        try:
            line = _prompt("calc> ")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line or line.lower() in {"quit", "exit", "q"}:
            print("Goodbye!")
            break
        parts = line.split()
        if len(parts) != 3:
            print("Usage: <number> <operator> <number>  (e.g. 2 + 3)")
            continue
        try:
            a = float(parts[0])
            op = parts[1]
            b = float(parts[2])
            result = calculate(a, op, b)
        except ValueError as exc:
            print(f"Error: {exc}")
            continue
        except ZeroDivisionError as exc:
            print(f"Error: {exc}")
            continue
        # Display integers without a trailing ".0".
        print(result if result != int(result) else int(result))


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Usage:
        python tools/calculator.py <number> <operator> <number>
        python tools/calculator.py        # interactive REPL
    """
    args = sys.argv[1:] if argv is None else argv
    if not args:
        repl()
        return 0
    if len(args) != 3:
        print("Usage: python tools/calculator.py <number> <operator> <number>")
        print("       python tools/calculator.py        # interactive REPL")
        return 1
    try:
        a = float(args[0])
        op = args[1]
        b = float(args[2])
        result = calculate(a, op, b)
    except ValueError as exc:
        print(f"Error: {exc}")
        return 1
    except ZeroDivisionError as exc:
        print(f"Error: {exc}")
        return 1
    print(result if result != int(result) else int(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
