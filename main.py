#!/usr/bin/env python3
# ZoteBoat: Empires Beyond
# Python stdlib only.

from __future__ import annotations
import json, os, sys, math, random, traceback
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Callable

# -------------------------
# Errors
# -------------------------

class ZoteError(Exception):
    def __init__(self, msg: str, file: str = "<unknown>", line: int = 1, col: int = 1):
        super().__init__(f"{file}:{line}:{col}: {msg}")
        self.file = file
        self.line = line
        self.col = col
        self.msg = msg

# -------------------------
# Lexer
# -------------------------

@dataclass
class Tok:
    t: str
    v: Any
    line: int
    col: int

KEYWORDS = {
    "let","fn","if","else","while","for","in","range",
    "return","break","continue","import",
    "true","false","null","and","or"
}

SINGLE = {
    "(": "LP", ")": "RP",
    "{": "LB", "}": "RB",
    "[": "LS", "]": "RS",
    ",": "COM", ";": "SEM", ":": "COL"
}

DOUBLE = {
    "==":"EQ", "!=":"NE", "<=":"LE", ">=":"GE"
}

class Lexer:
    def __init__(self, src: str, file: str):
        self.s = src
        self.file = file
        self.i = 0
        self.line = 1
        self.col = 1

    def _peek(self, n=0) -> str:
        j = self.i + n
        return self.s[j] if j < len(self.s) else ""

    def _adv(self) -> str:
        ch = self._peek()
        self.i += 1
        if ch == "\n":
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return ch

    def _err(self, msg: str) -> ZoteError:
        return ZoteError(msg, self.file, self.line, self.col)

    def tokens(self) -> List[Tok]:
        out: List[Tok] = []
        while self.i < len(self.s):
            ch = self._peek()
            if ch in " \t\r\n":
                self._adv()
                continue
            if ch == "#":
                while self._peek() and self._peek() != "\n":
                    self._adv()
                continue

            line, col = self.line, self.col

            # two-char ops
            two = ch + self._peek(1)
            if two in DOUBLE:
                self._adv(); self._adv()
                out.append(Tok(DOUBLE[two], two, line, col))
                continue

            # single-char punctuation
            if ch in SINGLE:
                self._adv()
                out.append(Tok(SINGLE[ch], ch, line, col))
                continue

            # one-char ops
            if ch in "+-*/%<>!=":
                self._adv()
                out.append(Tok("OP", ch, line, col))
                continue

            # string
            if ch == '"':
                self._adv()
                buf = []
                while True:
                    c = self._peek()
                    if c == "":
                        raise self._err("Unterminated string")
                    if c == '"':
                        self._adv()
                        break
                    if c == "\\":
                        self._adv()
                        esc = self._peek()
                        if esc == "n":
                            self._adv(); buf.append("\n")
                        elif esc == "t":
                            self._adv(); buf.append("\t")
                        elif esc == '"':
                            self._adv(); buf.append('"')
                        elif esc == "\\":
                            self._adv(); buf.append("\\")
                        else:
                            raise self._err(f"Unknown escape \\{esc}")
                        continue
                    buf.append(self._adv())
                out.append(Tok("STR", "".join(buf), line, col))
                continue

            # number
            if ch.isdigit():
                buf = [self._adv()]
                is_float = False
                while self._peek().isdigit():
                    buf.append(self._adv())
                if self._peek() == "." and self._peek(1).isdigit():
                    is_float = True
                    buf.append(self._adv())
                    while self._peek().isdigit():
                        buf.append(self._adv())
                txt = "".join(buf)
                out.append(Tok("NUM", float(txt) if is_float else int(txt), line, col))
                continue

            # identifier / keyword
            if ch.isalpha() or ch == "_":
                buf = [self._adv()]
                while (self._peek().isalnum() or self._peek() == "_"):
                    buf.append(self._adv())
                name = "".join(buf)
                if name in KEYWORDS:
                    out.append(Tok(name.upper(), name, line, col))
                else:
                    out.append(Tok("ID", name, line, col))
                continue

            raise self._err(f"Unexpected character: {ch!r}")

        out.append(Tok("EOF", None, self.line, self.col))
        return out

# -------------------------
# AST Nodes
# -------------------------

@dataclass
class Node: tok: Tok

@dataclass
class Program(Node): body: List[Node]

@dataclass
class Block(Node): body: List[Node]

@dataclass
class Import(Node): path: str

@dataclass
class Let(Node): name: str; expr: Node

@dataclass
class Assign(Node): target: Node; expr: Node  # target is Var or Index

@dataclass
class Var(Node): name: str

@dataclass
class Index(Node): obj: Node; key: Node

@dataclass
class Literal(Node): value: Any

@dataclass
class ListLit(Node): items: List[Node]

@dataclass
class MapLit(Node): items: List[Tuple[str, Node]]  # string keys only

@dataclass
class If(Node): cond: Node; then_b: Block; else_b: Optional[Block]

@dataclass
class While(Node): cond: Node; body: Block

@dataclass
class ForRange(Node): name: str; start: Node; end: Node; body: Block

@dataclass
class Fn(Node): name: str; params: List[str]; body: Block

@dataclass
class Call(Node): fn: Node; args: List[Node]

@dataclass
class Return(Node): expr: Optional[Node]

@dataclass
class Break(Node): pass

@dataclass
class Continue(Node): pass

@dataclass
class ExprStmt(Node): expr: Node

@dataclass
class Unary(Node): op: str; expr: Node

@dataclass
class Binary(Node): op: str; a: Node; b: Node

# -------------------------
# Parser
# -------------------------

class Parser:
    def __init__(self, toks: List[Tok], file: str):
        self.toks = toks
        self.file = file
        self.i = 0

    def _peek(self, n=0) -> Tok:
        j = self.i + n
        return self.toks[j] if j < len(self.toks) else self.toks[-1]

    def _eat(self, t: str) -> Tok:
        tok = self._peek()
        if tok.t != t:
            raise ZoteError(f"Expected {t}, got {tok.t}", self.file, tok.line, tok.col)
        self.i += 1
        return tok

    def _match(self, *types: str) -> Optional[Tok]:
        tok = self._peek()
        if tok.t in types:
            self.i += 1
            return tok
        return None

    def parse(self) -> Program:
        body: List[Node] = []
        start = self._peek()
        while self._peek().t != "EOF":
            body.append(self.stmt())
        return Program(start, body)

    def stmt(self) -> Node:
        tok = self._peek()
        if self._match("SEM"):
            return ExprStmt(tok, Literal(tok, None))

        if self._match("IMPORT"):
            p = self._eat("STR")
            self._eat("SEM")
            return Import(tok, p.v)

        if self._match("LET"):
            name = self._eat("ID")
            self._eat("OP")  # '=' as OP
            expr = self.expr()
            self._eat("SEM")
            return Let(tok, name.v, expr)

        if self._match("FN"):
            name = self._eat("ID")
            self._eat("LP")
            params: List[str] = []
            if self._peek().t != "RP":
                params.append(self._eat("ID").v)
                while self._match("COM"):
                    params.append(self._eat("ID").v)
            self._eat("RP")
            body = self.block()
            return Fn(tok, name.v, params, body)

        if self._match("RETURN"):
            if self._peek().t == "SEM":
                self._eat("SEM")
                return Return(tok, None)
            expr = self.expr()
            self._eat("SEM")
            return Return(tok, expr)

        if self._match("BREAK"):
            self._eat("SEM")
            return Break(tok)

        if self._match("CONTINUE"):
            self._eat("SEM")
            return Continue(tok)

        if self._match("IF"):
            cond = self.expr()
            then_b = self.block()
            else_b = None
            if self._match("ELSE"):
                else_b = self.block()
            return If(tok, cond, then_b, else_b)

        if self._match("WHILE"):
            cond = self.expr()
            body = self.block()
            return While(tok, cond, body)

        if self._match("FOR"):
            name = self._eat("ID").v
            self._eat("IN")
            self._eat("RANGE")
            self._eat("LP")
            start = self.expr()
            self._eat("COM")
            end = self.expr()
            self._eat("RP")
            body = self.block()
            return ForRange(tok, name, start, end, body)

        # assignment or expression statement
        expr = self.expr()
        if self._match("OP") and self.toks[self.i-1].v == "=":
            rhs = self.expr()
            self._eat("SEM")
            return Assign(tok, expr, rhs)
        self._eat("SEM")
        return ExprStmt(tok, expr)

    def block(self) -> Block:
        tok = self._eat("LB")
        body: List[Node] = []
        while self._peek().t != "RB":
            body.append(self.stmt())
        self._eat("RB")
        return Block(tok, body)

    # Expression parsing (precedence climbing)
    def expr(self) -> Node:
        return self.logic_or()

    def logic_or(self) -> Node:
        node = self.logic_and()
        while self._match("OR"):
            op = self.toks[self.i-1]
            node = Binary(op, "or", node, self.logic_and())
        return node

    def logic_and(self) -> Node:
        node = self.equality()
        while self._match("AND"):
            op = self.toks[self.i-1]
            node = Binary(op, "and", node, self.equality())
        return node

    def equality(self) -> Node:
        node = self.compare()
        while True:
            if self._match("EQ"):
                op = self.toks[self.i-1]
                node = Binary(op, "==", node, self.compare())
            elif self._match("NE"):
                op = self.toks[self.i-1]
                node = Binary(op, "!=", node, self.compare())
            else:
                break
        return node

    def compare(self) -> Node:
        node = self.term()
        while True:
            if self._match("LE"):
                op = self.toks[self.i-1]; node = Binary(op, "<=", node, self.term())
            elif self._match("GE"):
                op = self.toks[self.i-1]; node = Binary(op, ">=", node, self.term())
            elif self._peek().t == "OP" and self._peek().v in "<>":
                op = self._eat("OP")
                node = Binary(op, op.v, node, self.term())
            else:
                break
        return node

    def term(self) -> Node:
        node = self.factor()
        while self._peek().t == "OP" and self._peek().v in "+-":
            op = self._eat("OP")
            node = Binary(op, op.v, node, self.factor())
        return node

    def factor(self) -> Node:
        node = self.unary()
        while self._peek().t == "OP" and self._peek().v in "*/%":
            op = self._eat("OP")
            node = Binary(op, op.v, node, self.unary())
        return node

    def unary(self) -> Node:
        if self._peek().t == "OP" and self._peek().v in "-!":
            op = self._eat("OP")
            return Unary(op, op.v, self.unary())
        return self.call()


    def call(self) -> Node:
        node = self.primary()
        while True:
            if self._match("LP"):
                args: List[Node] = []
                if self._peek().t != "RP":
                    args.append(self.expr())
                    while self._match("COM"):
                        args.append(self.expr())
                self._eat("RP")
                node = Call(node.tok, node, args)
            elif self._match("LS"):
                key = self.expr()
                self._eat("RS")
                node = Index(node.tok, node, key)
            else:
                break
        return node

    def primary(self) -> Node:
        tok = self._peek()
        if self._match("NUM"):
            return Literal(tok, tok.v)
        if self._match("STR"):
            return Literal(tok, tok.v)
        if self._match("TRUE"):
            return Literal(tok, True)
        if self._match("FALSE"):
            return Literal(tok, False)
        if self._match("NULL"):
            return Literal(tok, None)
        if self._match("ID"):
            return Var(tok, tok.v)
        if self._match("LP"):
            node = self.expr()
            self._eat("RP")
            return node
        if self._match("LS"):
            items: List[Node] = []
            if self._peek().t != "RS":
                items.append(self.expr())
                while self._match("COM"):
                    items.append(self.expr())
            self._eat("RS")
            return ListLit(tok, items)
        if self._match("LB"):
            # map literal: {"k": expr, ...}
            items: List[Tuple[str, Node]] = []
            if self._peek().t != "RB":
                k = self._eat("STR").v
                self._eat("COL")
                v = self.expr()
                items.append((k, v))
                while self._match("COM"):
                    k = self._eat("STR").v
                    self._eat("COL")
                    v = self.expr()
                    items.append((k, v))
            self._eat("RB")
            return MapLit(tok, items)

        raise ZoteError(f"Unexpected token {tok.t}", self.file, tok.line, tok.col)

# -------------------------
# Runtime Values
# -------------------------

class ReturnSig(Exception):
    def __init__(self, value: Any):
        self.value = value

class BreakSig(Exception): pass
class ContinueSig(Exception): pass

@dataclass
class ZoteFn:
    name: str
    params: List[str]
    body: Block
    env: Dict[str, Any]   # module/global env
    file: str

@dataclass
class NativeFn:
    name: str
    arity: Optional[int]
    fn: Callable[..., Any]

def truthy(v: Any) -> bool:
    if v is None: return False
    if v is False: return False
    if v == 0 or v == 0.0: return False
    if v == "": return False
    if isinstance(v, (list, dict)) and len(v) == 0: return False
    return True

def num_binop(op: str, a: Any, b: Any, tok: Tok, file: str) -> Any:
    if not isinstance(a, (int,float)) or not isinstance(b, (int,float)):
        raise ZoteError(f"Operator {op} requires numbers", file, tok.line, tok.col)
    if op == "+": return a + b
    if op == "-": return a - b
    if op == "*": return a * b
    if op == "/":
        if b == 0: raise ZoteError("Division by zero", file, tok.line, tok.col)
        return a / b
    if op == "%":
        if not isinstance(a,int) or not isinstance(b,int):
            raise ZoteError("% requires ints", file, tok.line, tok.col)
        if b == 0: raise ZoteError("Modulo by zero", file, tok.line, tok.col)
        return a % b
    raise ZoteError(f"Unknown op {op}", file, tok.line, tok.col)

def describe_action(a: dict) -> str:
    kind = a.get("kind", "unknown")

    if kind == "policy":
        return f"Enact policy '{a.get('policy')}' on faction '{a.get('faction')}'"

    if kind == "repeal_policy":
        return f"Repeal policy '{a.get('policy')}' on faction '{a.get('faction')}'"

    if kind == "research":
        return f"Research tech '{a.get('tech')}' for faction '{a.get('faction')}'"

    if kind == "treaty":
        return f"Propose treaty '{a.get('treaty')}' between '{a.get('a')}' and '{a.get('b')}'"

    if kind == "break_treaty":
        return f"Break treaty between '{a.get('a')}' and '{a.get('b')}'"

    if kind == "trade":
        give = a.get("give", {})
        take = a.get("take", {})
        return (f"Trade deal: '{a.get('a')}' gives {give} "
                f"to '{a.get('b')}' for {take}")

    if kind == "war":
        return f"Declare war: '{a.get('a')}' vs '{a.get('b')}'"

    if kind == "peace":
        return f"Offer peace between '{a.get('a')}' and '{a.get('b')}'"

    if kind == "espionage":
        return (f"Espionage: '{a.get('actor')}' targets '{a.get('target')}' "
                f"mission='{a.get('mission')}'")

    if kind == "space_build":
        return f"Build habitat '{a.get('habitat')}' controlled by '{a.get('faction')}'"

    if kind == "space_ship":
        cargo = a.get("cargo", {})
        return (f"Ship cargo {cargo} from '{a.get('from')}' "
                f"to habitat '{a.get('to')}'")

    if kind == "space_research":
        return f"Space research '{a.get('tech')}' for faction '{a.get('faction')}'"

    return f"{kind}: {a}"


def fmt_num(x):
    if isinstance(x, float):
        return f"{x:.1f}"
    return str(x)

def safe_get(d, *keys, default=None):
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur

def top_dashboard(state: dict, debug: bool = False) -> str:
    fs = state.get("factions", {})
    names = sorted(fs.keys())

    mkt = state.get("market", {})
    infl = mkt.get("inflation", 0.0)

    wars = state.get("wars", [])
    treaties = state.get("treaties", [])

    sp = state.get("space", {})
    space_unlocked = sp.get("unlocked", False)
    habs = safe_get(sp, "habitats", default={}) or {}
    collapsed = sum(1 for h in habs.values() if isinstance(h, dict) and h.get("status") == "collapsed")

    lines = []
    lines.append(f"=== TOP (Turn {state.get('turn')}) ===")
    lines.append(f"Market: inflation={fmt_num(infl)} | Wars={len(wars)} | Treaties={len(treaties)} | Space={'UNLOCKED' if space_unlocked else 'LOCKED'} | Habitats={len(habs)} (collapsed={collapsed})")
    lines.append("")

    # header
    lines.append("Faction | Pop | Morale | Unrest | Credits | Food | Water | Energy | Units" + (" | rho | duo(o,h)" if debug else ""))
    lines.append("-" * (92 if not debug else 120))

    for n in names:
        f = fs[n]
        res = f.get("resources", {})
        pop = f.get("pop", 0)
        morale = res.get("morale", 0)
        unrest = f.get("unrest", 0)
        credits = res.get("credits", 0)
        food = res.get("food", 0)
        water = res.get("water", 0)
        energy = res.get("energy", 0)
        units = res.get("units", 0)

        row = f"{n} | {pop} | {fmt_num(morale)} | {fmt_num(unrest)} | {fmt_num(credits)} | {fmt_num(food)} | {fmt_num(water)} | {fmt_num(energy)} | {fmt_num(units)}"

        if debug:
            rho = f.get("rho", 0.0)
            duo = f.get("duology", {}) or {}
            row += f" | {fmt_num(rho)} | ({fmt_num(duo.get('o',0))},{fmt_num(duo.get('h',0))})"

        lines.append(row)

    lines.append("")
    if wars:
        lines.append("Active wars:")
        for w in wars:
            lines.append(f"  - {w.get('a')} vs {w.get('b')} (months={w.get('months')})")
    else:
        lines.append("Active wars: none")

    if treaties:
        lines.append("Treaties:")
        for t in treaties:
            lines.append(f"  - {t.get('kind')}: {t.get('a')} <-> {t.get('b')} (ttl={t.get('ttl')})")
    else:
        lines.append("Treaties: none")

    return "\n".join(lines)


def cmd_help() -> str:
    return (
        "Commands:\n"
        "  new [seed]            start a new game\n"
        "  show                  summary view\n"
        "  factions              list factions\n"
        "  faction <name>        detailed faction view\n"
        "  research              researched tech per faction\n"
        "  policies              active policies per faction\n"
        "  wars                  list active wars\n"
        "  treaties              list treaties\n"
        "  market                macro economy\n"
        "  actions               show numbered actions\n"
        "  do <i>                take action i and advance one turn\n"
        "  tick                  advance one turn without action\n"
        "  space                 space ops summary\n"
        "  save <file>           save game JSON\n"
        "  load <file>           load game JSON\n"
        "  replay <file>         replay from saved seed+actions\n"
        "  hash                  deterministic state hash\n"
        "  quit                  exit\n"
    )

def fmt_resources(res: dict) -> str:
    # show core first, then others
    core = ["food","water","energy","metal","silicon","credits","influence","morale","units","parts"]
    parts = []
    for k in core:
        if k in res:
            v = res[k]
            if isinstance(v, float):
                parts.append(f"{k}={v:.1f}")
            else:
                parts.append(f"{k}={v}")
    # any extra keys
    extras = [k for k in res.keys() if k not in core]
    extras.sort()
    for k in extras:
        parts.append(f"{k}={res[k]}")
    return ", ".join(parts)

def show_factions(state: dict) -> str:
    fs = state.get("factions", {})
    names = sorted(fs.keys())
    lines = ["Factions:"]
    for n in names:
        f = fs[n]
        lines.append(f"  - {n} (pop={f.get('pop')}, morale={f.get('resources',{}).get('morale')}, unrest={f.get('unrest')})")
    return "\n".join(lines)

def show_one_faction(state: dict, name: str, debug: bool = False) -> str:
    fs = state.get("factions", {})
    f = fs.get(name)
    if not f:
        # try case-insensitive match
        for k in fs.keys():
            if k.lower() == name.lower():
                f = fs[k]
                name = k
                break
    if not f:
        return f"Unknown faction '{name}'. Try: factions"

    res = f.get("resources", {})
    tech = f.get("tech", {})
    pol = f.get("policies", {})

    tech_done = [k for k,v in tech.items() if v == 1]
    tech_done.sort()

    pol_on = [k for k,v in pol.items() if v]
    pol_on.sort()

    lines = [
        f"{name}",
        f"  pop={f.get('pop')}  morale={res.get('morale')}  unrest={f.get('unrest')}",
        f"  war_exhaust={f.get('war_exhaust')}  intel={f.get('intel')}",
        f"  resources: {fmt_resources(res)}",
        f"  tech: {', '.join(tech_done) if tech_done else '(none)'}",
        f"  policies: {', '.join(pol_on) if pol_on else '(none)'}",
    ]

    if debug:
        duo = f.get("duology", {})
        lines.append(f"  (hidden) rho={f.get('rho')} duo=(o={duo.get('o')}, h={duo.get('h')})")

    return "\n".join(lines)

def show_research(state: dict) -> str:
    fs = state.get("factions", {})
    names = sorted(fs.keys())
    lines = ["Research status:"]
    for n in names:
        tech = fs[n].get("tech", {})
        done = [k for k,v in tech.items() if v == 1]
        done.sort()
        lines.append(f"  - {n}: {', '.join(done) if done else '(none)'}")
    return "\n".join(lines)

def show_policies(state: dict) -> str:
    fs = state.get("factions", {})
    names = sorted(fs.keys())
    lines = ["Policies active:"]
    for n in names:
        pol = fs[n].get("policies", {})
        on = [k for k,v in pol.items() if v]
        on.sort()
        lines.append(f"  - {n}: {', '.join(on) if on else '(none)'}")
    return "\n".join(lines)

def show_wars(state: dict) -> str:
    wars = state.get("wars", [])
    if not wars:
        return "Wars: none"
    lines = ["Wars:"]
    for i, w in enumerate(wars):
        a = w.get("a"); b = w.get("b")
        months = w.get("months", 0)
        al = w.get("a_losses", 0.0)
        bl = w.get("b_losses", 0.0)
        lines.append(f"  [{i}] {a} vs {b} | months={months} | losses: {a}={al:.1f}, {b}={bl:.1f}")
    return "\n".join(lines)

def show_treaties(state: dict) -> str:
    ts = state.get("treaties", [])
    if not ts:
        return "Treaties: none"
    lines = ["Treaties:"]
    for i, t in enumerate(ts):
        kind = t.get("kind")
        a = t.get("a"); b = t.get("b")
        ttl = t.get("ttl")
        lines.append(f"  [{i}] {kind} | {a} <-> {b} | ttl={ttl}")
    return "\n".join(lines)


def action_involved_factions(a: dict) -> list[str]:
    # returns list of faction names involved in an action
    kind = a.get("kind")

    if "faction" in a and isinstance(a["faction"], str):
        return [a["faction"]]

    # diplomacy/war/trade style (a,b)
    if "a" in a and "b" in a:
        out = []
        if isinstance(a.get("a"), str): out.append(a["a"])
        if isinstance(a.get("b"), str): out.append(a["b"])
        return out

    # space actions might reference faction or habitat; habitat owner not trivial here
    if kind in {"build_hab", "set_space_budget"} and isinstance(a.get("faction"), str):
        return [a["faction"]]

    return []

def normalize_faction_name(state: dict, name: str) -> str | None:
    fs = state.get("factions", {})
    if name in fs:
        return name
    low = name.lower()
    for k in fs.keys():
        if k.lower() == low:
            return k
    return None

def group_actions_by_faction(state: dict, actions: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {}
    for a in actions:
        involved = action_involved_factions(a)
        if not involved:
            involved = ["(global)"]
        for f in involved:
            groups.setdefault(f, []).append(a)
    # stable ordering
    for k in list(groups.keys()):
        groups[k] = groups[k]
    return groups


def show_market(state: dict) -> str:
    m = state.get("market", {})
    infl = m.get("inflation")
    csg = m.get("credit_supply_growth")
    mb = m.get("metal_backing")
    return (
        "Market:\n"
        f"  inflation={infl}\n"
        f"  credit_supply_growth={csg}\n"
        f"  metal_backing={mb}"
    )


# -------------------------
# Interpreter
# -------------------------

class Runtime:
    def __init__(self, root_dir: str, debug: bool = False):
        self.root_dir = root_dir
        self.debug_enabled = debug
        self.module_cache: Dict[str, Dict[str, Any]] = {}
        self.rng = random.Random(0)
        self.event_sink: List[Dict[str, Any]] = []

    def load_module(self, path: str) -> Dict[str, Any]:
        norm = os.path.normpath(os.path.join(self.root_dir, path))
        if norm in self.module_cache:
            return self.module_cache[norm]
        if not os.path.exists(norm):
            raise ZoteError(f"Module not found: {path}", path, 1, 1)
        with open(norm, "r", encoding="utf-8") as f:
            src = f.read()
        toks = Lexer(src, path).tokens()
        ast = Parser(toks, path).parse()
        env: Dict[str, Any] = {}
        self._install_stdlib(env)
        self.module_cache[norm] = env
        self.exec_program(ast, env, path)
        return env

    def _install_stdlib(self, env: Dict[str, Any]) -> None:
        # IO
        env["print"] = NativeFn("print", None, lambda *args: print(*args))
        env["input"] = NativeFn("input", 1, lambda prompt: input(str(prompt)))

        # basic utils
        env["len"] = NativeFn("len", 1, lambda x: len(x))
        env["keys"] = NativeFn("keys", 1, lambda m: list(m.keys()))
        env["has"] = NativeFn("has", 2, lambda m,k: (k in m))
        env["push"] = NativeFn("push", 2, lambda lst,v: (lst.append(v), None)[1])
        env["pop"]  = NativeFn("pop", 1, lambda lst: (lst.pop() if lst else None))
        env["str"]  = NativeFn("str", 1, lambda x: str(x))
        env["num"]  = NativeFn("num", 1, lambda x: float(x) if (("." in str(x)) or ("e" in str(x).lower())) else int(x))
        env["floor"]= NativeFn("floor", 1, lambda x: int(math.floor(float(x))))
        env["abs"]  = NativeFn("abs", 1, lambda x: abs(x))
        env["min"]  = NativeFn("min", 2, lambda a,b: a if a < b else b)
        env["max"]  = NativeFn("max", 2, lambda a,b: a if a > b else b)
        env["clamp"]= NativeFn("clamp", 3, lambda x,lo,hi: lo if x<lo else (hi if x>hi else x))

        # RNG
        env["rng_seed"] = NativeFn("rng_seed", 1, self._rng_seed)
        env["rng_int"]  = NativeFn("rng_int", 2, self._rng_int)
        env["rng_float"]= NativeFn("rng_float", 0, self._rng_float)
        env["rng_choice"]= NativeFn("rng_choice", 1, self._rng_choice)

        # hooks
        env["emit_event"] = NativeFn("emit_event", 2, self._emit_event)
        env["debug"] = NativeFn("debug", 1, self._debug)

    def _rng_seed(self, n: Any) -> None:
        self.rng.seed(int(n)); return None

    def _rng_int(self, lo: Any, hi: Any) -> int:
        return self.rng.randint(int(lo), int(hi))

    def _rng_float(self) -> float:
        return self.rng.random()

    def _rng_choice(self, xs: Any) -> Any:
        if not isinstance(xs, list) or not xs:
            return None
        return xs[self.rng.randrange(0, len(xs))]

    def _emit_event(self, tag: Any, payload: Any) -> None:
        self.event_sink.append({"tag": str(tag), "payload": payload})
        return None

    def _debug(self, msg: Any) -> None:
        if self.debug_enabled:
            print(f"[DEBUG] {msg}")
        return None

    def exec_program(self, prog: Program, env: Dict[str, Any], file: str) -> None:
        for st in prog.body:
            self.exec_stmt(st, env, env, file)

    def exec_block(self, block: Block, local: Dict[str, Any], env: Dict[str, Any], file: str) -> None:
        for st in block.body:
            self.exec_stmt(st, local, env, file)

    def exec_stmt(self, node: Node, local: Dict[str, Any], env: Dict[str, Any], file: str) -> None:
        if isinstance(node, Import):
            imported = self.load_module(node.path)
            # merge: imported names become available in this module
            # do not overwrite existing names (local module wins)
            for k, v in imported.items():
                if k not in env:
                    env[k] = v
            return
        if isinstance(node, Let):
            local[node.name] = self.eval_expr(node.expr, local, env, file)
            return
        if isinstance(node, Fn):
            local[node.name] = ZoteFn(node.name, node.params, node.body, env, file)
            return
        if isinstance(node, Assign):
            val = self.eval_expr(node.expr, local, env, file)
            self._assign(node.target, val, local, env, file)
            return
        if isinstance(node, If):
            if truthy(self.eval_expr(node.cond, local, env, file)):
                self.exec_block(node.then_b, local, env, file)
            elif node.else_b:
                self.exec_block(node.else_b, local, env, file)
            return
        if isinstance(node, While):
            while truthy(self.eval_expr(node.cond, local, env, file)):
                try:
                    self.exec_block(node.body, local, env, file)
                except ContinueSig:
                    continue
                except BreakSig:
                    break
            return
        if isinstance(node, ForRange):
            a = self.eval_expr(node.start, local, env, file)
            b = self.eval_expr(node.end, local, env, file)
            if not isinstance(a, (int,float)) or not isinstance(b, (int,float)):
                raise ZoteError("range(a,b) requires numbers", file, node.tok.line, node.tok.col)
            ia, ib = int(a), int(b)
            for i in range(ia, ib):
                local[node.name] = i
                try:
                    self.exec_block(node.body, local, env, file)
                except ContinueSig:
                    continue
                except BreakSig:
                    break
            return
        if isinstance(node, Return):
            val = None if node.expr is None else self.eval_expr(node.expr, local, env, file)
            raise ReturnSig(val)
        if isinstance(node, Break):
            raise BreakSig()
        if isinstance(node, Continue):
            raise ContinueSig()
        if isinstance(node, ExprStmt):
            self.eval_expr(node.expr, local, env, file)
            return
        raise ZoteError(f"Unknown statement node {type(node)}", file, node.tok.line, node.tok.col)

    def _assign(self, target: Node, val: Any, local: Dict[str, Any], env: Dict[str, Any], file: str) -> None:
        if isinstance(target, Var):
            if target.name in local:
                local[target.name] = val
            elif target.name in env:
                env[target.name] = val
            else:
                # implicit global if not local?
                local[target.name] = val
            return
        if isinstance(target, Index):
            obj = self.eval_expr(target.obj, local, env, file)
            key = self.eval_expr(target.key, local, env, file)
            if isinstance(obj, list):
                if not isinstance(key, (int,float)):
                    raise ZoteError("List index must be number", file, target.tok.line, target.tok.col)
                idx = int(key)
                if idx < 0 or idx >= len(obj):
                    raise ZoteError("List index out of range", file, target.tok.line, target.tok.col)
                obj[idx] = val
                return
            if isinstance(obj, dict):
                obj[key] = val
                return
            raise ZoteError("Index assignment target must be list or map", file, target.tok.line, target.tok.col)
        raise ZoteError("Invalid assignment target", file, target.tok.line, target.tok.col)

    def eval_expr(self, node: Node, local: Dict[str, Any], env: Dict[str, Any], file: str) -> Any:
        if isinstance(node, Literal):
            return node.value
        if isinstance(node, Var):
            if node.name in local: return local[node.name]
            if node.name in env: return env[node.name]
            raise ZoteError(f"Undefined variable '{node.name}'", file, node.tok.line, node.tok.col)
        if isinstance(node, ListLit):
            return [self.eval_expr(x, local, env, file) for x in node.items]
        if isinstance(node, MapLit):
            m: Dict[Any, Any] = {}
            for k, vexpr in node.items:
                m[k] = self.eval_expr(vexpr, local, env, file)
            return m
        if isinstance(node, Index):
            obj = self.eval_expr(node.obj, local, env, file)
            key = self.eval_expr(node.key, local, env, file)
            if isinstance(obj, list):
                idx = int(key)
                if idx < 0 or idx >= len(obj):
                    return None
                return obj[idx]
            if isinstance(obj, dict):
                return obj.get(key, None)
            raise ZoteError("Indexing requires list or map", file, node.tok.line, node.tok.col)
        if isinstance(node, Unary):
            v = self.eval_expr(node.expr, local, env, file)
            if node.op == "-":
                if not isinstance(v, (int,float)):
                    raise ZoteError("Unary - requires number", file, node.tok.line, node.tok.col)
                return -v
            if node.op == "!":
                return not truthy(v)
            raise ZoteError(f"Unknown unary {node.op}", file, node.tok.line, node.tok.col)
        if isinstance(node, Binary):
            if node.op == "and":
                a = self.eval_expr(node.a, local, env, file)
                return self.eval_expr(node.b, local, env, file) if truthy(a) else a
            if node.op == "or":
                a = self.eval_expr(node.a, local, env, file)
                return a if truthy(a) else self.eval_expr(node.b, local, env, file)

            a = self.eval_expr(node.a, local, env, file)
            b = self.eval_expr(node.b, local, env, file)

            if node.op in {"+","-","*","/","%"}:
                # string concat for +
                if node.op == "+" and (isinstance(a, str) or isinstance(b, str)):
                    return str(a) + str(b)
                return num_binop(node.op, a, b, node.tok, file)

            if node.op in {"==","!="}:
                return (a == b) if node.op == "==" else (a != b)
            if node.op in {"<",">","<=",">="}:
                if not isinstance(a, (int,float,str)) or not isinstance(b, (int,float,str)):
                    raise ZoteError(f"Compare {node.op} requires comparable types", file, node.tok.line, node.tok.col)
                if node.op == "<": return a < b
                if node.op == ">": return a > b
                if node.op == "<=": return a <= b
                if node.op == ">=": return a >= b
            raise ZoteError(f"Unknown binary {node.op}", file, node.tok.line, node.tok.col)
        if isinstance(node, Call):
            fnv = self.eval_expr(node.fn, local, env, file)
            args = [self.eval_expr(a, local, env, file) for a in node.args]
            return self._call(fnv, args, node.tok, file)
        raise ZoteError(f"Unknown expr node {type(node)}", file, node.tok.line, node.tok.col)

    def _call(self, fnv: Any, args: List[Any], tok: Tok, file: str) -> Any:
        if isinstance(fnv, NativeFn):
            if fnv.arity is not None and len(args) != fnv.arity:
                raise ZoteError(f"{fnv.name} expects {fnv.arity} args", file, tok.line, tok.col)
            try:
                return fnv.fn(*args)
            except ZoteError:
                raise
            except Exception as e:
                raise ZoteError(f"Native error in {fnv.name}: {e}", file, tok.line, tok.col)
        if isinstance(fnv, ZoteFn):
            if len(args) != len(fnv.params):
                raise ZoteError(f"{fnv.name} expects {len(fnv.params)} args", file, tok.line, tok.col)
            call_locals: Dict[str, Any] = {}
            for p, a in zip(fnv.params, args):
                call_locals[p] = a
            try:
                self.exec_block(fnv.body, call_locals, fnv.env, fnv.file)
            except ReturnSig as r:
                return r.value
            return None
        raise ZoteError("Attempted to call non-function", file, tok.line, tok.col)

# -------------------------
# Game Runner (CLI)
# -------------------------

def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def ensure_rules_exist(root: str) -> None:
    # just a friendly message; user creates files from this response
    req = [
        "rules/main.zs","rules/math_system.zs","rules/factions.zs","rules/economy.zs",
        "rules/diplomacy.zs","rules/war.zs","rules/tech.zs","rules/events.zs","rules/space.zs"
    ]
    missing = [p for p in req if not os.path.exists(os.path.join(root, p))]
    if missing:
        print("Missing rule files:")
        for m in missing: print(" -", m)
        print("Create them from the project spec output, then rerun.")
        sys.exit(1)

def state_hash(obj: Any) -> str:
    s = json.dumps(obj, sort_keys=True, separators=(",",":"))
    # cheap deterministic hash
    h = 2166136261
    for ch in s.encode("utf-8"):
        h ^= ch
        h = (h * 16777619) & 0xFFFFFFFF
    return hex(h)

def main():
    root = os.path.dirname(os.path.abspath(__file__))
    ensure_rules_exist(root)

    debug = "--debug" in sys.argv
    fast  = "--fast" in sys.argv

    rt = Runtime(root_dir=root, debug=debug)
    env = rt.load_module("rules/main.zs")

    def zs_call(name: str, *args):
        fnv = env.get(name)
        if fnv is None:
            raise ZoteError(f"Missing required function {name}", "rules/main.zs", 1, 1)
        return rt._call(fnv, list(args), Tok("ID", name, 1,1), "rules/main.zs")

    # CLI commands
    print("ZoteBoat: Empires Beyond (CLI)")
    print("Commands: new [seed], load <file>, save <file>, replay <file>, quit")

    state = None
    actions_log: List[Dict[str, Any]] = []
    seed = 0
    last_actions = []
    last_actions_label = "none"


    while True:
        cmd = input("> ").strip().split()
        if not cmd:
            continue
        if cmd[0] == "quit":
            return

        if cmd[0] == "new":
            seed = int(cmd[1]) if len(cmd) > 1 else 12345
            rt.event_sink.clear()
            zs_call("rng_seed", seed)  # stdlib RNG
            state = zs_call("init_game", seed)
            actions_log = []
            print("New game created. Seed:", seed)
            last_actions = []
            last_actions_label = "none"
            continue

        if cmd[0] == "save" and state is not None:
            path = cmd[1] if len(cmd)>1 else "save.json"
            blob = {"seed": seed, "state": zs_call("serialize", state), "actions": actions_log}
            with open(path, "w", encoding="utf-8") as f:
                json.dump(blob, f, indent=2, sort_keys=True)
            print("Saved:", path)
            continue

        if cmd[0] == "load":
            path = cmd[1] if len(cmd)>1 else "save.json"
            blob = json.loads(read_text(path))
            seed = int(blob["seed"])
            zs_call("rng_seed", seed)
            state = zs_call("deserialize", blob["state"])
            actions_log = blob.get("actions", [])
            print("Loaded:", path, "Seed:", seed, "Turns:", len(actions_log))
            last_actions = []
            last_actions_label = "none"
            continue

        if cmd[0] == "replay":
            path = cmd[1] if len(cmd)>1 else "save.json"
            blob = json.loads(read_text(path))
            seed = int(blob["seed"])
            zs_call("rng_seed", seed)
            state = zs_call("init_game", seed)
            for a in blob.get("actions", []):
                state = zs_call("apply_action", state, a)
                out = zs_call("tick", state)
                state = out["state"]
            print("Replay done. Final hash:", state_hash(zs_call("serialize", state)))
            continue

        if state is None:
            print("Start a game with: new [seed]")
            continue

        # in-game commands
        if cmd[0] == "show":
            out = zs_call("ui_summary", state, debug)
            print(out)
            continue

        # Keep these variables near the top of main(), before the while loop:
        # last_actions = []
        # last_actions_label = "all"

        if cmd[0] == "actions":
            # Always regenerate actions fresh from state
            all_acts = zs_call("available_actions", state)

            # Parse filter target:
            # - "actions"                => grouped by faction
            # - "actions all"            => flat list all
            # - "actions <Faction Name>" => only actions involving that faction
            arg = " ".join(cmd[1:]).strip() if len(cmd) > 1 else ""

            if arg.lower() == "all":
                last_actions = all_acts
                last_actions_label = "all"
                for i, a in enumerate(last_actions):
                    print(f"[{i}] {describe_action(a)}")
                continue

            if arg:
                fname = normalize_faction_name(state, arg)
                if not fname:
                    print(f"Unknown faction '{arg}'. Try: factions")
                    continue

                filtered = []
                for a in all_acts:  # <-- FIX: filter from fresh action list
                    inv = action_involved_factions(a)
                    if fname in inv:
                        filtered.append(a)

                last_actions = filtered
                last_actions_label = fname
                print(f"Actions involving {fname}:")
                for i, a in enumerate(last_actions):
                    print(f"[{i}] {describe_action(a)}")
                continue

            # Default: grouped by faction
            groups = group_actions_by_faction(state, all_acts)

            # We'll also build a single flattened list that matches printed indices.
            flat = []
            keys_sorted = sorted(groups.keys(), key=lambda x: (x == "(global)", x))

            print("Actions (grouped). Tip: `actions <Faction Name>` to filter, or `actions all` for flat list.")
            for g in keys_sorted:
                print(f"\n== {g} ==")
                for a in groups[g]:
                    flat.append(a)
                    print(f"[{len(flat) - 1}] {describe_action(a)}")

            last_actions = flat
            last_actions_label = "grouped"
            continue

        if cmd[0] == "do":
            if len(cmd) < 2:
                print("Usage: do <action_index>")
                continue

            if not last_actions:
                last_actions = zs_call("available_actions", state)
                last_actions_label = "auto"

            try:
                idx = int(cmd[1])
            except ValueError:
                print("Bad index (must be an integer).")
                continue

            if idx < 0 or idx >= len(last_actions):
                print(f"Bad index. You have {len(last_actions)} actions listed (view: {last_actions_label}).")
                continue

            action = last_actions[idx]
            state = zs_call("apply_action", state, action)
            actions_log.append(action)

            out = zs_call("tick", state)
            state = out["state"]
            log = out["log"]

            if rt.event_sink:
                log = log + [f"EVENT[{e['tag']}]: {e['payload']}" for e in rt.event_sink]
                rt.event_sink.clear()

            print("\n".join([str(x) for x in log]))
            continue

        if cmd[0] == "help":
            print(cmd_help())
            continue

        if cmd[0] == "factions":
            print(show_factions(state))
            continue

        if cmd[0] == "faction":
            if len(cmd) < 2:
                print("Usage: faction <name>")
                continue
            name = " ".join(cmd[1:])
            print(show_one_faction(state, name, debug=debug))
            continue


        if cmd[0] == "research":
            print(show_research(state))
            continue

        if cmd[0] == "policies":
            print(show_policies(state))
            continue

        if cmd[0] == "wars":
            print(show_wars(state))
            continue

        if cmd[0] == "treaties":
            print(show_treaties(state))
            continue

        if cmd[0] == "market":
            print(show_market(state))
            continue


        if cmd[0] == "space":
            out = zs_call("ui_space", state, debug)
            print(out)
            continue

        if cmd[0] == "top":
            print(top_dashboard(state, debug=debug))
            continue

        if cmd[0] == "tick":
            # no-op tick (useful for tests)
            out = zs_call("tick", state)
            state = out["state"]
            log = out["log"]
            last_actions = []
            last_actions_label = "none"
            print("\n".join([str(x) for x in log]))
            continue

        if cmd[0] == "hash":
            print(state_hash(zs_call("serialize", state)))
            continue

        print("Commands: show, actions, do <i>, tick, save <f>, load <f>, replay <f>, hash, quit")

if __name__ == "__main__":
    try:
        main()
    except ZoteError as ze:
        print("ZoteError:", ze)
        sys.exit(2)
    except Exception:
        traceback.print_exc()
        sys.exit(3)
