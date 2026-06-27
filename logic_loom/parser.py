"""A small Pratt parser that turns math text into :class:`Expr` trees.

Supports:  + - * / ^   unary minus   parentheses   function calls
           numeric literals   variables   ?pattern-variables

The same parser is used for user expressions and for rewrite-rule
patterns, so a rule like ``"?a*?b + ?a*?c"`` is parsed by exactly the
same code path as ``"a*b + a*c"``.
"""

from __future__ import annotations

from typing import List, Optional

from .expr import Expr


# --------------------------------------------------------------------- #
# Tokenizer
# --------------------------------------------------------------------- #
class Token:
    __slots__ = ("kind", "text")

    def __init__(self, kind: str, text: str):
        self.kind = kind
        self.text = text

    def __repr__(self):  # pragma: no cover - debug helper
        return f"Token({self.kind!r}, {self.text!r})"


_PUNCT = set("+-*/^(),")


def tokenize(src: str) -> List[Token]:
    toks: List[Token] = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        if c.isspace():
            i += 1
            continue
        if c in _PUNCT:
            toks.append(Token(c, c))
            i += 1
            continue
        if c == "?":  # pattern variable: ?name
            j = i + 1
            while j < n and (src[j].isalnum() or src[j] == "_"):
                j += 1
            toks.append(Token("patvar", src[i + 1:j]))
            i = j
            continue
        if c.isdigit() or (c == "." and i + 1 < n and src[i + 1].isdigit()):
            j = i
            while j < n and (src[j].isdigit() or src[j] == "."):
                j += 1
            toks.append(Token("num", src[i:j]))
            i = j
            continue
        if c.isalpha() or c == "_":
            j = i
            while j < n and (src[j].isalnum() or src[j] == "_"):
                j += 1
            toks.append(Token("name", src[i:j]))
            i = j
            continue
        raise SyntaxError(f"Unexpected character {c!r} at position {i}")
    toks.append(Token("eof", ""))
    return toks


# --------------------------------------------------------------------- #
# Pratt parser
# --------------------------------------------------------------------- #
# (left binding power, right binding power) per infix operator.
_BP = {
    "+": (10, 11),
    "-": (10, 11),
    "*": (20, 21),
    "/": (20, 21),
    "^": (31, 30),   # right-associative -> right bp < left bp
}


class Parser:
    def __init__(self, toks: List[Token]):
        self.toks = toks
        self.pos = 0

    def peek(self) -> Token:
        return self.toks[self.pos]

    def next(self) -> Token:
        t = self.toks[self.pos]
        self.pos += 1
        return t

    def expect(self, kind: str) -> Token:
        t = self.next()
        if t.kind != kind:
            raise SyntaxError(f"Expected {kind!r} but got {t.kind!r} ({t.text!r})")
        return t

    def parse(self) -> Expr:
        e = self.expr(0)
        self.expect("eof")
        return e

    def expr(self, min_bp: int) -> Expr:
        left = self.nud()
        while True:
            op = self.peek()
            if op.kind not in _BP:
                break
            lbp, rbp = _BP[op.kind]
            if lbp < min_bp:
                break
            self.next()
            right = self.expr(rbp)
            left = Expr.app(op.kind, left, right)
        return left

    def nud(self) -> Expr:
        """Null denotation: prefixes, literals and grouping."""
        t = self.next()
        if t.kind == "num":
            text = t.text
            value: float | int = float(text) if "." in text else int(text)
            return Expr.num(value)
        if t.kind == "patvar":
            return Expr.patvar(t.text)
        if t.kind == "name":
            if self.peek().kind == "(":      # function call
                self.next()
                args = self._arglist()
                return Expr.app(t.text, *args)
            return Expr.var(t.text)
        if t.kind == "(":
            e = self.expr(0)
            self.expect(")")
            return e
        if t.kind == "-":                    # unary minus
            operand = self.expr(29)          # binds tighter than * but looser than ^
            return Expr.app("neg", operand)
        if t.kind == "+":                    # unary plus, harmless
            return self.expr(29)
        raise SyntaxError(f"Unexpected token {t.kind!r} ({t.text!r})")

    def _arglist(self) -> List[Expr]:
        args: List[Expr] = []
        if self.peek().kind == ")":
            self.next()
            return args
        while True:
            args.append(self.expr(0))
            t = self.next()
            if t.kind == ")":
                break
            if t.kind != ",":
                raise SyntaxError(f"Expected ',' or ')' but got {t.kind!r}")
        return args


def parse(src: str) -> Expr:
    """Parse a string into an :class:`Expr`."""
    return Parser(tokenize(src)).parse()
