"""Chain raw chords into polylines.

PDF exporters (KOMPAS among them) write every chord of a curve as a separate
path, so object identity is lost. Chords sharing an endpoint are re-joined
into polylines, stopping at branch points (where three or more chords meet),
which are corners or junctions of different objects.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass

from ..pdf.vector_extractor import RawSegment

NODE_TOLERANCE = 0.13  # mm; coordinates are quantised to ~0.085 mm (1/300")


@dataclass
class Chain:
    points: list[tuple[float, float]]
    width: float
    closed: bool

    @property
    def length(self) -> float:
        return sum(math.dist(a, b) for a, b in zip(self.points, self.points[1:]))


class _NodeIndex:
    """Merge vertices closer than ``tol`` into one node (grid hashing)."""

    def __init__(self, tol: float):
        self.tol = tol
        self.grid: dict[tuple[int, int], list[int]] = defaultdict(list)
        self.coords: list[tuple[float, float]] = []

    def node(self, p: tuple[float, float]) -> int:
        gx, gy = int(math.floor(p[0] / self.tol)), int(math.floor(p[1] / self.tol))
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for idx in self.grid[(gx + dx, gy + dy)]:
                    if math.dist(self.coords[idx], p) <= self.tol:
                        return idx
        self.coords.append(p)
        self.grid[(gx, gy)].append(len(self.coords) - 1)
        return len(self.coords) - 1


def build_chains(segments: list[RawSegment], tol: float = NODE_TOLERANCE) -> list[Chain]:
    """Group segments of equal stroke width into maximal non-branching chains."""
    by_width: dict[float, list[RawSegment]] = defaultdict(list)
    for s in segments:
        by_width[round(s.width, 2)].append(s)

    chains: list[Chain] = []
    for width, segs in by_width.items():
        index = _NodeIndex(tol)
        edges: list[tuple[int, int]] = []
        for s in segs:
            a, b = index.node(s.a), index.node(s.b)
            if a != b:
                edges.append((a, b))
        chains.extend(_walk(edges, index.coords, width))
    return chains


def _walk(edges, coords, width) -> list[Chain]:
    adjacency: dict[int, list[int]] = defaultdict(list)  # node -> edge ids
    for i, (a, b) in enumerate(edges):
        adjacency[a].append(i)
        adjacency[b].append(i)
    used = [False] * len(edges)

    def other(edge_id, node):
        a, b = edges[edge_id]
        return b if a == node else a

    def extend(path_nodes):
        while True:
            node = path_nodes[-1]
            if len(adjacency[node]) != 2:
                return
            nxt = [e for e in adjacency[node] if not used[e]]
            if not nxt:
                return
            used[nxt[0]] = True
            path_nodes.append(other(nxt[0], node))

    chains = []
    # Start from chain ends and branch points first, then the remaining loops.
    starts = sorted(adjacency, key=lambda n: len(adjacency[n]) == 2)
    for start in starts:
        for e in adjacency[start]:
            if used[e]:
                continue
            used[e] = True
            nodes = [start, other(e, start)]
            extend(nodes)
            closed = nodes[0] == nodes[-1] and len(nodes) > 2
            chains.append(Chain([coords[n] for n in nodes], width, closed))
    return chains
