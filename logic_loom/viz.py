"""Render an e-graph as Graphviz DOT for inspection.

Seeing the e-graph is the best way to understand what equality saturation
actually does: every dashed box is an *e-class* (a set of forms known to
be equal), and the nodes inside it are the different ways to build a value
in that class.  Edges point from an operator to the classes of its
operands.

    from logic_loom import build_egraph, to_dot
    eg, root, _ = build_egraph("a*b + a*c")
    open("egraph.dot", "w").write(to_dot(eg, root))
    # then:  dot -Tsvg egraph.dot -o egraph.svg
"""

from __future__ import annotations

from .egraph import EGraph


def _label(head) -> str:
    if isinstance(head, str):
        return head.replace('"', r"\"")
    if isinstance(head, float) and head.is_integer():
        head = int(head)
    return str(head)


def to_dot(eg: EGraph, root: int | None = None) -> str:
    lines = [
        "digraph egraph {",
        "  compound=true;",
        "  rankdir=BT;",
        "  node [shape=box, fontname=monospace];",
    ]
    node_id = {}
    counter = 0

    for cid in eg.eclasses():
        if cid not in eg.classes:
            continue
        canon = eg.find(cid)
        is_root = root is not None and eg.find(root) == canon
        lines.append(f"  subgraph cluster_{canon} {{")
        lines.append("    style=dashed;")
        lines.append(f'    color="{"#2b8a3e" if is_root else "#adb5bd"}";')
        lines.append(f'    label="class {canon}{" (root)" if is_root else ""}";')
        for node in eg.nodes_of(canon):
            head, args = node
            key = (canon, node)
            node_id[key] = f"n{counter}"
            lines.append(f'    n{counter} [label="{_label(head)}"];')
            counter += 1
        lines.append("  }")

    # edges from operator nodes to the clusters of their operands
    for cid in eg.eclasses():
        if cid not in eg.classes:
            continue
        canon = eg.find(cid)
        for node in eg.nodes_of(canon):
            head, args = node
            src = node_id[(canon, node)]
            for child in args:
                ch = eg.find(child)
                # point at any node in the child cluster, then clamp to cluster
                target = next(iter(eg.nodes_of(ch)))
                dst = node_id[(ch, target)]
                lines.append(f"  {src} -> {dst} [lhead=cluster_{ch}];")

    lines.append("}")
    return "\n".join(lines)
