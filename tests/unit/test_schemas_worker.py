"""Tests for backend/schemas/worker.py."""

from datetime import datetime, timezone

from backend.schemas.worker import WorkerNodeRead


def test_worker_node_read_from_attributes():
    now = datetime.now(timezone.utc)
    data = {
        "id": "worker-1",
        "worker_id": "celery@hostname",
        "hostname": "myhost",
        "status": "online",
        "active_tasks": 3,
        "last_heartbeat": now,
        "created_at": now,
        "updated_at": now,
    }
    worker = WorkerNodeRead(**data)
    assert worker.id == "worker-1"
    assert worker.worker_id == "celery@hostname"
    assert worker.hostname == "myhost"
    assert worker.status == "online"
    assert worker.active_tasks == 3
    assert worker.last_heartbeat == now


def test_worker_node_read_no_heartbeat():
    now = datetime.now(timezone.utc)
    worker = WorkerNodeRead(
        id="w2",
        worker_id="celery@host2",
        hostname="host2",
        status="offline",
        active_tasks=0,
        last_heartbeat=None,
        created_at=now,
        updated_at=now,
    )
    assert worker.last_heartbeat is None
    assert worker.active_tasks == 0
