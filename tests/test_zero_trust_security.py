# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2026 Dmitrii Gagarin aka madgagarin

import time

from rxon.models import (
    Heartbeat,
    SecurityContext,
    TaskResult,
    WorkerEventPayload,
    WorkerRegistration,
)
from rxon.security import sign_payload, verify_signature
from rxon.utils import from_dict, to_dict


def test_sign_and_verify_payload_basic():
    """Test basic HMAC SHA256 signing and verification."""
    payload = {"worker_id": "test-worker", "status": "active"}
    secret = "super-secret-key"

    signature = sign_payload(payload, secret)
    assert isinstance(signature, str)
    assert len(signature) > 10

    # Verify should succeed
    assert verify_signature(payload, signature, secret) is True

    # Tampering should fail
    tampered_payload = {"worker_id": "test-worker", "status": "hacked"}
    assert verify_signature(tampered_payload, signature, secret) is False

    # Wrong secret should fail
    assert verify_signature(payload, signature, "wrong-secret") is False


def test_worker_registration_zero_trust_fields():
    """Test WorkerRegistration handles timestamp and security fields."""
    ts = time.time()
    security = SecurityContext(signature="test-sig", signer_id="worker-1")
    reg = WorkerRegistration(worker_id="worker-1", worker_type="test", timestamp=ts, security=security)

    reg_dict = to_dict(reg)
    assert reg_dict["timestamp"] == ts
    assert reg_dict["security"]["signature"] == "test-sig"
    assert reg_dict["security"]["signer_id"] == "worker-1"

    # Restore from dict
    restored = from_dict(WorkerRegistration, reg_dict)
    assert restored.timestamp == ts
    assert restored.security.signature == "test-sig"
    assert restored.security.signer_id == "worker-1"


def test_task_result_zero_trust_fields():
    """Test TaskResult handles timestamp and security fields."""
    ts = time.time()
    security = SecurityContext(signature="test-sig", signer_id="worker-1")
    res = TaskResult(job_id="j1", task_id="t1", worker_id="worker-1", status="success", timestamp=ts, security=security)

    res_dict = to_dict(res)
    assert res_dict["timestamp"] == ts
    assert res_dict["security"]["signature"] == "test-sig"

    restored = from_dict(TaskResult, res_dict)
    assert restored.timestamp == ts
    assert restored.security.signature == "test-sig"


def test_heartbeat_zero_trust_fields():
    """Test Heartbeat handles timestamp and security fields."""
    ts = time.time()
    security = SecurityContext(signature="test-sig", signer_id="worker-1")
    hb = Heartbeat(worker_id="worker-1", status="ready", timestamp=ts, security=security)

    hb_dict = to_dict(hb)
    assert hb_dict["timestamp"] == ts
    assert hb_dict["security"]["signature"] == "test-sig"

    restored = from_dict(Heartbeat, hb_dict)
    assert restored.timestamp == ts
    assert restored.security.signature == "test-sig"


def test_worker_event_payload_zero_trust_fields():
    """Test WorkerEventPayload handles timestamp and security fields."""
    ts = time.time()
    security = SecurityContext(signature="test-sig", signer_id="worker-1")
    event = WorkerEventPayload(
        event_id="e1",
        worker_id="worker-1",
        origin_worker_id="worker-1",
        event_type="progress",
        payload={"progress": 50},
        timestamp=ts,
        security=security,
        bubbling_chain=["proxy-1"],
    )

    event_dict = to_dict(event)
    assert event_dict["timestamp"] == ts
    assert event_dict["security"]["signature"] == "test-sig"
    assert "proxy-1" in event_dict["bubbling_chain"]

    restored = from_dict(WorkerEventPayload, event_dict)
    assert restored.timestamp == ts
    assert restored.security.signature == "test-sig"
    assert restored.bubbling_chain == ["proxy-1"]
