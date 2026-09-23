#!/usr/bin/env python3
"""
Aritmetica di intervalli temporali [(start, end), ...] in secondi.
Usata dal report della pulizia take e dal banco di prova.
"""

from typing import List, Tuple

Interval = Tuple[float, float]


def union(intervals) -> List[Interval]:
    """Unisce intervalli sovrapposti o adiacenti; scarta quelli vuoti."""
    items = sorted((s, e) for s, e in intervals if e > s)
    merged: List[Interval] = []
    for s, e in items:
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    return merged


def measure(intervals) -> float:
    """Durata coperta dagli intervalli (le sovrapposizioni contano una volta)."""
    return sum(e - s for s, e in union(intervals))


def complement(intervals, duration: float) -> List[Interval]:
    """Parti di [0, duration] non coperte dagli intervalli."""
    out: List[Interval] = []
    pos = 0.0
    for s, e in union(intervals):
        s = min(max(s, 0.0), duration)
        e = min(e, duration)
        if s > pos:
            out.append((pos, s))
        pos = max(pos, e)
    if pos < duration:
        out.append((pos, duration))
    return out


def intersect(a, b) -> List[Interval]:
    """Intersezione di due insiemi di intervalli."""
    a, b = union(a), union(b)
    out: List[Interval] = []
    i = j = 0
    while i < len(a) and j < len(b):
        s = max(a[i][0], b[j][0])
        e = min(a[i][1], b[j][1])
        if e > s:
            out.append((s, e))
        if a[i][1] < b[j][1]:
            i += 1
        else:
            j += 1
    return out


def subtract(a, b) -> List[Interval]:
    """Parti di a non coperte da b."""
    a = union(a)
    if not a:
        return []
    end = max(e for _, e in a)
    return intersect(a, complement(b, end))
