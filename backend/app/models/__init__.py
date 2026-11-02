"""SQLAlchemy models. Importing this package registers every table on Base.metadata."""
from app.models.base import Base, utcnow
from app.models.core import AuditLog, Department, SystemSetting, User, UserSession, user_departments
from app.models.customers import Customer, CustomerContact
from app.models.forms import FormDefinition, FormField, RequestType
from app.models.integration import IntegrationLog, IntegrationMapping
from app.models.notifications import TicketNotification
from app.models.tickets import (
    Ticket,
    TicketAssignment,
    TicketAttachment,
    TicketComment,
    TicketDetail,
    TicketSequence,
    TicketStatusHistory,
    TicketTrackingToken,
)
from app.models.workflow import AssignmentRule, TicketStatus, WorkflowTransition

__all__ = [
    "AssignmentRule",
    "AuditLog",
    "Base",
    "Customer",
    "CustomerContact",
    "Department",
    "FormDefinition",
    "FormField",
    "IntegrationLog",
    "IntegrationMapping",
    "RequestType",
    "SystemSetting",
    "Ticket",
    "TicketAssignment",
    "TicketAttachment",
    "TicketComment",
    "TicketDetail",
    "TicketNotification",
    "TicketSequence",
    "TicketStatus",
    "TicketStatusHistory",
    "TicketTrackingToken",
    "User",
    "UserSession",
    "WorkflowTransition",
    "user_departments",
    "utcnow",
]
