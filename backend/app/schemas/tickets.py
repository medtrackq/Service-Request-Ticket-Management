from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class StatusRef(BaseModel):
    code: str
    name_th: str
    name_en: str
    category: str
    color: str


class NamedRef(BaseModel):
    id: int
    code: str | None = None
    name_th: str | None = None
    name_en: str | None = None


class UserRef(BaseModel):
    id: int
    full_name: str


class TicketListItem(BaseModel):
    id: int
    ticket_number: str
    created_at: datetime
    last_activity_at: datetime
    customer_name: str
    contact_name: str
    request_type_code: str
    request_type_name_th: str
    request_type_name_en: str
    subject: str
    priority: str
    status: StatusRef
    department: NamedRef
    assigned_user: UserRef | None
    due_at: datetime | None
    is_overdue: bool
    is_sample: bool


class DetailValue(BaseModel):
    key: str
    label_th: str
    label_en: str
    value: str | None


class AttachmentOut(ORMModel):
    id: uuid.UUID
    original_filename: str
    mime_type: str
    size_bytes: int
    kind: str
    width: int | None
    height: int | None
    source: str
    comment_id: int | None
    uploaded_by_name: str | None = None
    created_at: datetime
    url: str


class HistoryOut(BaseModel):
    id: int
    created_at: datetime
    from_status: str | None
    to_status: str
    actor_type: str
    actor_name: str | None
    comment: str | None


class AssignmentOut(BaseModel):
    id: int
    created_at: datetime
    assignment_type: str
    from_department: str | None
    to_department: str
    from_user: str | None
    to_user: str | None
    assigned_by: str | None
    priority: str | None
    due_at: datetime | None
    reason: str | None


class CommentOut(BaseModel):
    id: int
    created_at: datetime
    author_type: str
    author_name: str | None
    visibility: str
    body: str


class TransitionOut(BaseModel):
    to_status: str
    name_th: str
    name_en: str
    requires_comment: bool


class TicketPermissions(BaseModel):
    can_change_status: bool
    can_assign: bool
    can_self_assign: bool
    can_transfer: bool
    can_comment: bool
    can_upload: bool
    can_regenerate_token: bool


class CustomerOut(BaseModel):
    id: int
    name: str
    customer_type: str
    code: str | None


class ContactOut(BaseModel):
    id: int
    name: str
    department: str | None
    phone: str | None
    email: str | None


class TicketDetailOut(BaseModel):
    id: int
    ticket_number: str
    request_type: NamedRef
    subject: str
    description: str
    category: str | None
    priority: str
    status: StatusRef
    source: str
    created_at: datetime
    updated_at: datetime
    last_activity_at: datetime
    due_at: datetime | None
    first_response_at: datetime | None
    resolved_at: datetime | None
    closed_at: datetime | None
    cancelled_at: datetime | None
    is_overdue: bool
    is_sample: bool
    anonymized_at: datetime | None
    privacy_consent_version: str | None
    privacy_consent_at: datetime | None
    customer: CustomerOut
    contact: ContactOut
    department: NamedRef
    assigned_user: UserRef | None
    details: list[DetailValue]
    attachments: list[AttachmentOut]
    history: list[HistoryOut]
    assignments: list[AssignmentOut]
    comments: list[CommentOut]
    allowed_transitions: list[TransitionOut]
    permissions: TicketPermissions


class StatusChangeIn(BaseModel):
    to_status: str = Field(max_length=30)
    comment: str | None = Field(default=None, max_length=5000)
    public_message: str | None = Field(default=None, max_length=5000)


class AssignIn(BaseModel):
    department_id: int | None = None
    assigned_user_id: int | None = None
    unassign: bool = False
    priority: str | None = None
    due_at: datetime | None = None
    reason: str | None = Field(default=None, max_length=2000)


class BulkAssignIn(AssignIn):
    ticket_ids: list[int] = Field(min_length=1, max_length=200)


class BulkResult(BaseModel):
    updated: list[str]
    failed: list[dict[str, Any]]


class CommentIn(BaseModel):
    body: str = Field(min_length=1, max_length=5000)
    visibility: str = Field(pattern="^(INTERNAL|PUBLIC)$")


class TokenOut(BaseModel):
    ticket_number: str
    tracking_token: str
    tracking_url: str
