"""Functional correctness tests for role-based healthcare access control."""

import pytest
from record_store import (
    PatientRecord,
    PatientRecordStore,
    SecurityContext,
)


@pytest.fixture
def populated_store():
    s = PatientRecordStore()
    s.insert_record(
        PatientRecord(
            record_id="rec-001",
            tenant_id="hospital-1",
            owner_id="patient-bob",
            patient_name="Bob Jones",
            clinical_notes="Hypertension stage 1.",
        )
    )
    return s


def test_doctor_in_same_tenant_can_access(populated_store):
    doc_ctx = SecurityContext(user_id="dr-house", tenant_id="hospital-1", role="doctor")
    rec = populated_store.get_record("rec-001", doc_ctx)
    assert rec.patient_name == "Bob Jones"


def test_admin_in_same_tenant_can_access(populated_store):
    admin_ctx = SecurityContext(user_id="admin-carl", tenant_id="hospital-1", role="admin")
    rec = populated_store.get_record("rec-001", admin_ctx)
    assert rec.patient_name == "Bob Jones"

