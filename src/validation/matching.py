"""Label matching, reusing the official scorer's normalisation (src/evaluate.py: norm + pairs_ok).

`pair_up` returns the matched index pairs (evaluate.match only returns counts and leftovers), using the same
maximum one-to-one matching, so "strict" and "lenient" mean exactly what they mean in the quality reports.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evaluate import norm, pairs_ok  # noqa: E402


def pair_up(left, right, lenient):
    """Maximum one-to-one matching between two label lists -> {left_index: right_index}."""
    a, b = [norm(x) for x in left], [norm(x) for x in right]
    edges = [[j for j, y in enumerate(b) if pairs_ok(x, y, lenient)] for x in a]
    owner = {}  # right index -> left index

    def augment(i, seen):
        for j in edges[i]:
            if j not in seen:
                seen.add(j)
                if j not in owner or augment(owner[j], seen):
                    owner[j] = i
                    return True
        return False

    for i in range(len(a)):
        augment(i, set())
    return {i: j for j, i in owner.items()}


def same_label(a, b, lenient=False):
    return pairs_ok(norm(a), norm(b), lenient)


def compare_annotation(reviewer_labels, gold_labels, model_extras=()):
    """Classify a submitted independent annotation against the existing gold labels of the posting.

    match              strict match with a gold label
    naming_difference  lenient-only match (same skill, different wording)
    reviewer_only      not in gold -> candidate omission (never automatically a gold error)
    shared_omission    reviewer_only AND not predicted by the model either (possible omission by both)
    gold_only          gold label the reviewer did not write -> candidate unsupported gold label
    ambiguous          a reviewer label that loosely matches 2+ gold labels
    """
    strict = pair_up(reviewer_labels, gold_labels, lenient=False)
    rest_r = [i for i in range(len(reviewer_labels)) if i not in strict]
    rest_g = [j for j in range(len(gold_labels)) if j not in set(strict.values())]
    loose = pair_up([reviewer_labels[i] for i in rest_r], [gold_labels[j] for j in rest_g], lenient=True)
    loose = {rest_r[i]: rest_g[j] for i, j in loose.items()}
    used_g = set(strict.values()) | set(loose.values())
    out = []
    for i, label in enumerate(reviewer_labels):
        many = sum(same_label(label, g, lenient=True) for g in gold_labels) >= 2
        if i in strict:
            kind, gold = "match", gold_labels[strict[i]]
        elif i in loose:
            kind, gold = "naming_difference", gold_labels[loose[i]]
        else:
            by_model = any(same_label(label, x, lenient=True) for x in model_extras)
            kind, gold = ("reviewer_only" if by_model else "shared_omission"), None
        out.append({"kind": kind, "reviewer_label": label, "gold_label": gold, "ambiguous": many})
    out += [{"kind": "gold_only", "reviewer_label": None, "gold_label": g, "ambiguous": False}
            for j, g in enumerate(gold_labels) if j not in used_g]
    return out
