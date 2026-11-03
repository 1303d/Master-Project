"""Deterministic sampling: same population + seed -> same sample on every machine and Python version."""
import random


def sample_ids(ids, k, seed):
    """k IDs from `ids`, independent of input order (sorted first), with a recorded seed."""
    population = sorted(set(ids))
    k = max(0, min(int(k), len(population)))
    return sorted(random.Random(seed).sample(population, k))


def sample_fraction(ids, fraction, seed):
    n = len(set(ids))
    k = round(n * float(fraction))
    if n and fraction > 0 and k == 0:
        k = 1
    return sample_ids(ids, k, seed)
