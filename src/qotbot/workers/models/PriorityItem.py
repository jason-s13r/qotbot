from dataclasses import dataclass, field


@dataclass(order=True)
class PriorityItem:
    priority: int
    timestamp: float = field(compare=True)
    item: dict = field(compare=False)