"""Multi-tenant patient record store with access control."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


class AuthorizationError(Exception):
    """Raised when an actor lacks permission to access the requested resource."""


class RecordNotFoundError(Exception):
    """Raised when a record does not exist."""


@dataclass(frozen=True)
class SecurityContext:
    user_id: str
    tenant_id: str
    role: str  # 'patient', 'doctor', 'admin'


@dataclass(frozen=True)
class PatientRecord:
    record_id: str
    tenant_id: str
    owner_id: str
    patient_name: str
    clinical_notes: str


class PatientRecordStore:
    """Store for managing patient health records."""

    def __init__(self) -> None:
        self._records: Dict[str, PatientRecord] = {}

    def insert_record(self, record: PatientRecord) -> None:
        self._records[record.record_id] = record

    def get_record(self, record_id: str, context: SecurityContext) -> PatientRecord:
        """Retrieves a patient record.

        VULNERABILITY: Does not verify that context.tenant_id matches record.tenant_id,
        nor that context.user_id has permission to view record.owner_id's data.
        """
        if not isinstance(context, SecurityContext):
            raise TypeError("SecurityContext is required.")

        record = self._records.get(record_id)
        if record is None:
            raise RecordNotFoundError(f"Record '{record_id}' not found.")

        # VULNERABLE: Direct object reference without authorization check!
        return record

