from typing import Optional, List, Tuple
from cuas.common.messages import Track

EFFECTOR_BY_CLASS = {"quad": "E1", "fpv": "E2"}   # fixedwing -> None (E3, Phase 3)


def select_effector(trk: Track) -> Optional[str]:
    return EFFECTOR_BY_CLASS.get(trk.cls)


def in_no_fire(az_deg: float, arcs: List[Tuple[float, float]]) -> bool:
    a = az_deg % 360
    for lo, hi in arcs:
        lo %= 360
        hi %= 360
        if lo <= hi:
            if lo <= a <= hi:
                return True
        else:
            if a >= lo or a <= hi:
                return True
    return False


def firing_solution(trk: Track):
    """Мінімальне рішення: ефектор, азимут пуску, клас.
    Кутове наведення далі веде бортове бачення ефектора."""
    eff = select_effector(trk)
    return None if eff is None else {"effector": eff, "launch_az": trk.az_deg, "cls": trk.cls}
