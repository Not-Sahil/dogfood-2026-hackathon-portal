from collections import defaultdict


def bradley_terry_rankings(comparisons: list[tuple[int, int, int]], iterations: int = 60) -> list[dict]:
    """Return Bradley-Terry scores from (a, b, winner) comparisons.

    The implementation uses the standard MM update with a small epsilon,
    then normalizes scores into a relative 0-100 index for display.
    """
    items = sorted({item for comparison in comparisons for item in comparison[:2]})
    if not items:
        return []

    wins = defaultdict(float)
    matches = defaultdict(lambda: defaultdict(float))
    for a, b, winner in comparisons:
        if a == b or winner not in (a, b):
            continue
        wins[winner] += 1.0
        matches[a][b] += 1.0
        matches[b][a] += 1.0

    strength = {item: 1.0 for item in items}
    for _ in range(iterations):
        updated = {}
        for i in items:
            denom = 0.0
            for j, count in matches[i].items():
                denom += count / max(strength[i] + strength[j], 1e-9)
            updated[i] = wins[i] / denom if denom > 0 else strength[i]
        scale = sum(updated.values()) / len(updated) or 1.0
        strength = {i: max(updated[i] / scale, 1e-6) for i in items}

    ordered = sorted(items, key=lambda i: strength[i], reverse=True)
    top = max(strength.values()) or 1.0
    return [
        {"project_id": item, "bt_score": round(strength[item], 6), "relative_score": round(strength[item] / top * 100, 2), "rank": index + 1}
        for index, item in enumerate(ordered)
    ]
