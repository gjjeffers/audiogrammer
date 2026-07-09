from typing import Tuple


def dim(color: Tuple[int, int, int], factor: float) -> Tuple[int, int, int]:
    return tuple(max(0, int(c * factor)) for c in color)  # type: ignore[return-value]
