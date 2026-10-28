"""Security and authorization invariant tests for patient records."""

import pytest
from record_store import (
    AuthorizationError,
    PatientRecord,
    PatientRecordStore,
    SecurityContext,
)


@pytest.fixture
def multi_tenant_store():
    s = PatientRecordStore()
    # Tenant 1, Alice
    s.insert_record(
        PatientRecord(
            record_id="rec-alice",
            tenant_id="tenant-1",
            owner_id="user-alice",
            patient_name="Alice Confidential",
            clinical_notes="Confidential psychiatric notes.",
        )
    )
    # Tenant 1, Bob
    s.insert_record(
        PatientRecord(
            record_id="rec-bob",
            tenant_id="tenant-1",
            owner_id="user-bob",
            patient_name="Bob Public",
            clinical_notes="General physical exam.",
        )
    )
    # Tenant 2, Charlie
    s.insert_record(
        PatientRecord(
            record_id="rec-charlie",
            tenant_id="tenant-2",
            owner_id="user-charlie",
            patient_name="Charlie Outer",
            clinical_notes="Tenant 2 private record.",
        )
    )
    return s


def test_peer_patient_cannot_access_other_patient_record(multi_tenant_store):
    # Bob in tenant-1 attempts to read Alice's record in tenant-1
    bob_ctx = SecurityContext(user_id="user-bob", tenant_id="tenant-1", role="patient")
    with pytest.raises(AuthorizationError):
        multi_tenant_store.get_record("rec-alice", bob_ctx)


def test_cross_tenant_access_is_strictly_denied(multi_tenant_store):
    # Doctor in tenant-2 attempts to read record in tenant-1
    doc_t2 = SecurityContext(user_id="dr-tenant2", tenant_id="tenant-2", role="doctor")
    with pytest.raises(AuthorizationError):
        multi_tenant_store.get_record("rec-alice", doc_t2)


def test_cross_tenant_admin_access_is_denied(multi_tenant_store):
    # Admin in tenant-2 attempts to read record in tenant-1
    admin_t2 = SecurityContext(user_id="admin-tenant2", tenant_id="tenant-2", role="admin")
    with pytest.raises(AuthorizationError):
        multi_tenant_store.get_record("rec-alice", admin_t2)


def test_unauthorized_role_denied(multi_tenant_store):
    # Billing user in tenant-1 cannot view clinical notes
    billing_ctx = SecurityContext(user_id="user-billing", tenant_id="tenant-1", role="billing")
    with pytest.raises(AuthorizationError):
        multi_tenant_store.get_record("rec-alice", billing_ctx)

