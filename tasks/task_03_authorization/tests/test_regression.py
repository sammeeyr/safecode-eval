"""Regression tests for existing record store operations."""

import pytest
from record_store import (
    PatientRecord,
    PatientRecordStore,
    RecordNotFoundError,
    SecurityContext,
)


@pytest.fixture
def store():
    s = PatientRecordStore()
    s.insert_record(
        PatientRecord(
            record_id="rec-001",
            tenant_id="tenant-alpha",
            owner_id="user-alice",
            patient_name="Alice Smith",
            clinical_notes="Baseline vital statistics normal.",
        )
    )
    return s


def test_owner_can_retrieve_own_record(store):
    ctx = SecurityContext(user_id="user-alice", tenant_id="tenant-alpha", role="patient")
    record = store.get_record("rec-001", ctx)
    assert record.record_id == "rec-001"
    assert record.patient_name == "Alice Smith"


def test_missing_record_raises_not_found(store):
    ctx = SecurityContext(user_id="user-alice", tenant_id="tenant-alpha", role="patient")
    with pytest.raises(RecordNotFoundError):
        store.get_record("non-existent", ctx)


def test_invalid_context_raises_type_error(store):
    with pytest.raises(TypeError):
        store.get_record("rec-001", None)  # type: ignore

