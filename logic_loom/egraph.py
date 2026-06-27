"""A congruence-closure e-graph with rebuilding.

This is the data structure that lets Logic-Loom hold *many equivalent
forms of an expression at once* without exploding.  Equivalent terms
are grouped into **e-classes**; an **e-node** is one operator applied to
e-classes (not to concrete terms).  Because a node points at classes,
a single node such as ``+`` over ``{a*b}`` and ``{a*c}`` automatically
represents every term those classes contain.

The merge / ``rebuild`` algorithm follows the one described in
*"egg: Fast and Extensible Equality Saturation"* (Willsey et al., POPL
2021): unions are recorded eagerly and congruence is restored in
batches via a worklist, which keeps saturation fast.

E-node encoding
---------------
``(head, args)`` where ``args`` is a tuple of e-class ids.
* numeric literal -> ``(value, ())``      head is an int/float
* variable        -> ("x", ())            head is a str, no args
* application     -> ("+", (id1, id2))     head is a str, >=1 args
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Tuple

from .expr import Expr

ENode = Tuple[object, Tuple[int, ...]]


class EClass:
    __slots__ = ("nodes", "parents")

    def __init__(self):
        # The e-nodes that belong to this class.
        self.nodes: set[ENode] = set()
        # (e-node, owning-class-id) pairs that *mention* this class.
        self.parents: List[Tuple[ENode, int]] = []


class EGraph:
    def __init__(self):
        self._uf: Dict[int, int] = {}          # union-find parent pointers
        self.classes: Dict[int, EClass] = {}   # canonical id -> EClass
        self.hashcons: Dict[ENode, int] = {}   # canonical e-node -> class id
        self._worklist: List[int] = []
        self._next_id = 0

    # ----------------------------------------------------------------- #
    # union-find
    # ----------------------------------------------------------------- #
    def find(self, i: int) -> int:
        root = i
        while self._uf[root] != root:
            root = self._uf[root]
        # path compression
        while self._uf[i] != root:
            self._uf[i], i = root, self._uf[i]
        return root

    def _new_id(self) -> int:
        i = self._next_id
        self._next_id += 1
        self._uf[i] = i
        self.classes[i] = EClass()
        return i

    # ----------------------------------------------------------------- #
    # core operations
    # ----------------------------------------------------------------- #
    def _canon(self, node: ENode) -> ENode:
        head, args = node
        return (head, tuple(self.find(a) for a in args))

    def add_node(self, node: ENode) -> int:
        node = self._canon(node)
        if node in self.hashcons:
            return self.find(self.hashcons[node])
        eid = self._new_id()
        head, args = node
        for child in args:
            self.classes[self.find(child)].parents.append((node, eid))
        self.classes[eid].nodes.add(node)
        self.hashcons[node] = eid
        return eid

    def add_expr(self, e: Expr) -> int:
        """Insert a concrete (pattern-free) expression, return its class id."""
        if e.kind == "num":
            return self.add_node((e.value, ()))
        if e.kind == "var":
            return self.add_node((e.name, ()))
        if e.kind == "app":
            child_ids = tuple(self.add_expr(a) for a in e.args)
            return self.add_node((e.name, child_ids))
        raise ValueError(f"Cannot add pattern node of kind {e.kind!r} to e-graph")

    def merge(self, a: int, b: int) -> bool:
        """Union two classes. Returns True if they were not already equal."""
        a, b = self.find(a), self.find(b)
        if a == b:
            return False
        # Union by size: keep the larger class as the new root.
        if len(self.classes[a].parents) < len(self.classes[b].parents):
            a, b = b, a
        self._uf[b] = a
        # Fold b into a.
        self.classes[a].nodes |= self.classes[b].nodes
        self.classes[a].parents += self.classes[b].parents
        del self.classes[b]
        self._worklist.append(a)
        return True

    def rebuild(self) -> None:
        """Restore the congruence invariant after a batch of merges."""
        while self._worklist:
            todo = {self.find(i) for i in self._worklist}
            self._worklist.clear()
            for eid in todo:
                self._repair(eid)

    def _repair(self, eid: int) -> None:
        cls = self.classes[self.find(eid)]
        # Re-canonicalize parent e-nodes in the hashcons.
        for node, pid in cls.parents:
            self.hashcons.pop(node, None)
            canon = self._canon(node)
            self.hashcons[canon] = self.find(pid)
        # Merge parents that have become congruent.
        seen: Dict[ENode, int] = {}
        new_parents: List[Tuple[ENode, int]] = []
        for node, pid in cls.parents:
            canon = self._canon(node)
            if canon in seen:
                self.merge(pid, seen[canon])
            else:
                seen[canon] = self.find(pid)
                new_parents.append((canon, self.find(pid)))
        # Refresh this class's own node set to canonical form.
        cur = self.classes[self.find(eid)]
        cur.parents = new_parents
        cur.nodes = {self._canon(n) for n in cur.nodes}

    # ----------------------------------------------------------------- #
    # introspection helpers (used by matcher / extractor / folder)
    # ----------------------------------------------------------------- #
    def eclasses(self) -> Iterable[int]:
        return list(self.classes.keys())

    def nodes_of(self, eid: int) -> set[ENode]:
        return self.classes[self.find(eid)].nodes

    def num_nodes(self) -> int:
        return sum(len(c.nodes) for c in self.classes.values())
