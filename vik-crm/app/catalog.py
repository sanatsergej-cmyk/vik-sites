from dataclasses import dataclass


@dataclass(frozen=True)
class ServiceItem:
    id: str
    label: str
    priority: bool


# Приоритет Виталия (30.10.2026): земляные работы, монтаж трубопровода, монтаж кабеля, проектирование ИТП.
SERVICES = [
    ServiceItem("earthworks", "Земляные работы", True),
    ServiceItem("pipeline-install", "Монтаж трубопровода", True),
    ServiceItem("cable-install", "Монтаж кабеля", True),
    ServiceItem("itp-design", "Проектирование ИТП", True),
    ServiceItem("technical-customer", "Технический заказчик", False),
    ServiceItem("design", "Проектирование и согласования", False),
    ServiceItem("rso", "Согласование с РСО", False),
    ServiceItem("smr", "Строительно-монтажные работы", False),
    ServiceItem("handover", "Документация и сдача", False),
]
BY_ID = {s.id: s for s in SERVICES}


def label(service_id: str) -> str:
    item = BY_ID.get(service_id)
    return item.label if item else service_id


def is_priority(service_id: str) -> bool:
    item = BY_ID.get(service_id)
    return bool(item and item.priority)
