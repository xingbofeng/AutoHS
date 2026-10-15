from enum import Enum


class PositionIndexType(Enum):
    INVALID = 0,
    MY_HERO = 1,
    OPPO_HERO = 2,
    MY_MINION = 3,
    OPPO_MINION = 4,


class PositionIndex:
    def __init__(self, position_type: PositionIndexType, index: int):
        self.position_type = position_type
        self.index = index

    def __str__(self):
        return f"PositionIndex(type={self.position_type}, index={self.index})"

    def is_valid(self):
        return self.position_type != PositionIndexType.INVALID

    def is_my_minion(self):
        return self.position_type == PositionIndexType.MY_MINION
