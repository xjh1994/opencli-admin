from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.notifiers.base import AbstractNotifier

_REGISTRY: dict[str, "AbstractNotifier"] = {}


def register_notifier(cls: type) -> type:
    instance = cls()
    _REGISTRY[instance.notifier_type] = instance
    return cls


def get_notifier(notifier_type: str) -> "AbstractNotifier":
    if notifier_type not in _REGISTRY:
        raise ValueError(f"Unknown notifier type: {notifier_type!r}")
    return _REGISTRY[notifier_type]


def list_notifier_types() -> list[str]:
    return list(_REGISTRY.keys())


def _load_all_notifiers() -> None:
    from backend.notifiers import (  # noqa: F401
        dingtalk_notifier,
        email_notifier,
        feishu_notifier,
        wecom_notifier,
        webhook_notifier,
    )


_load_all_notifiers()
