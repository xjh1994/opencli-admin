from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.processors.base import AbstractProcessor

_REGISTRY: dict[str, "AbstractProcessor"] = {}


def register_processor(cls: type) -> type:
    instance = cls()
    _REGISTRY[instance.processor_type] = instance
    return cls


def get_processor(processor_type: str) -> "AbstractProcessor":
    if processor_type not in _REGISTRY:
        raise ValueError(f"Unknown processor type: {processor_type!r}")
    return _REGISTRY[processor_type]


def list_processor_types() -> list[str]:
    return list(_REGISTRY.keys())


def _load_all_processors() -> None:
    from backend.processors import (  # noqa: F401
        claude_processor,
        local_processor,
        openai_processor,
    )


_load_all_processors()
