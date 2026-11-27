"""Ordinal refinement of existing anonymous clone families, offline only.

Keeps the original clone-penalty formula while refining its relational key.
SPDX-License-Identifier: GPL-3.0-only
"""
from collections import Counter
from itertools import combinations


def ordinal_pattern(row):
    if len(row) != 7:
        raise ValueError('seven observations required')
    return tuple((3 if a is None and b is None else 4 if a is None else 5)
                 if a is None or b is None else (a > b) - (a < b)
                 for a, b in combinations(row, 2))


def clone_penalty(size, properties, alignment):
    # Exact baseline formula at 1c183c6, checked against every scored record.
    value = 10 if size >= 6 else 6 if size >= 4 else 3 if size >= 2 else 0
    if value and (properties['layout'] == 'single_blob'
                  or properties['scalar'] in ('medium', 'high')
                  or properties['text'] in ('medium', 'high')):
        value += 2
    if value and properties['layout'] == 'scattered' and alignment <= 2 and (
            size >= 4 or properties['scalar'] != '0' or properties['text'] != '0'):
        value += 2
    return value


def refine_clones(rows, families, alignments, original_penalties):
    """Return baseline-minus-refined penalties; no reference labels or IDs."""
    if not len(rows) == len(families) == len(alignments) == len(original_penalties):
        raise ValueError('population size mismatch')
    old_counts = Counter(families)
    properties = {family: dict(token.split(':', 1) for token in family.split('|'))
                  for family in old_counts}
    keys = [(family, ordinal_pattern(row)) for row, family in zip(rows, families)]
    counts = Counter(keys)
    output = []
    for family, key, alignment, old in zip(families, keys, alignments, original_penalties):
        if clone_penalty(old_counts[family], properties[family], alignment) != old:
            raise ValueError('baseline clone formula mismatch')
        output.append(old - clone_penalty(counts[key], properties[family], alignment))
    return output
