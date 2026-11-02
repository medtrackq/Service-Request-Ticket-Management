// Types mirroring the backend API (backend/app/api/routes/*, backend/app/schemas/*).

export type Lang = 'th' | 'en'
export type Priority = 'LOW' | 'NORMAL' | 'HIGH' | 'URGENT'
export type Role = 'ADMIN' | 'MANAGER' | 'STAFF'

export interface Named {
  name_th: string
  name_en: string
}

// ----------------------------------------------------------------- public

export interface PortalRequestType extends Named {
  code: string
  slug: string
  description_th: string | null
  description_en: string | null
  icon: string
}

export interface PortalConfig {
  settings: Record<string, string>
  liff_enabled: boolean
  request_types: PortalRequestType[]
}

export interface SelectOption {
  value: string
  label_th: string
  label_en: string
}

export type FieldType = 'text' | 'textarea' | 'number' | 'date' | 'select' | 'email' | 'tel' | 'file'

export interface FormFieldDef {
  key: string
  section: 'customer' | 'request' | 'attachments'
  field_type: FieldType
  label_th: string
  label_en: string
  placeholder_th: string | null
  placeholder_en: string | null
  help_th: string | null
  help_en: string | null
  required: boolean
  options: SelectOption[] | null
  validation: Record<string, unknown> | null
  maps_to: string | null
}

export interface FileRules {
  max_files: number
  max_size_mb: number
  accept: string[]
}

export interface PublicForm {
  id: number
  version: number
  title_th: string
  title_en: string
  request_type: Named & { code: string; slug: string; icon: string }
  file_rules: FileRules
  fields: FormFieldDef[]
}

export interface SubmissionResult extends Partial<Named> {
  ticket_number: string
  request_type_code: string
  request_type_name_th: string
  request_type_name_en: string
  subject: string
  created_at: string
  tracking_token: string | null
  tracking_url: string | null
  attachments: number
  replayed: boolean
}

export interface PublicTimelineEntry {
  type: 'STATUS' | 'MESSAGE'
  at: string
  status?: string
  status_name_th?: string
  status_name_en?: string
  author?: 'STAFF' | 'CUSTOMER'
  body?: string
}

export interface PublicTicketView {
  ticket_number: string
  request_type_code: string
  request_type_slug: string
  request_type_name_th: string
  request_type_name_en: string
  subject: string
  created_at: string
  status: string
  status_name_th: string
  status_name_en: string
  status_category: string
  can_reply: boolean
  has_attachments: boolean
  /** Remaining customer upload quota for this ticket (max_files) and allowed types. */
  reply_file_rules: FileRules
  timeline: PublicTimelineEntry[]
}

export interface PrivacyNotice {
  version: string
  text_th: string
  text_en: string
}

// ----------------------------------------------------------------- auth

export interface DepartmentRef extends Named {
  id: number
  code: string
}

export interface CurrentUser {
  id: number
  username: string
  full_name: string
  email: string | null
  role: Role
  preferred_language: Lang
  must_change_password: boolean
  departments: DepartmentRef[]
}

export interface Permissions {
  is_admin: boolean
  can_export: boolean
  can_view_reports: boolean
  can_bulk_assign: boolean
}

export interface AuthPayload {
  user: CurrentUser
  permissions: Permissions
  csrf_token: string
}

// ----------------------------------------------------------------- lookups

export interface StatusLookup extends Named {
  code: string
  category: string
  color: string
  is_terminal: boolean
}

export interface Lookups {
  departments: (DepartmentRef & { is_active: boolean })[]
  request_types: (Named & { id: number; code: string; slug: string })[]
  statuses: StatusLookup[]
  priorities: Priority[]
  customer_types: string[]
  users: { id: number; full_name: string; role: Role; department_ids: number[] }[]
}

// ----------------------------------------------------------------- tickets

export interface StatusRef extends Named {
  code: string
  category: string
  color: string
}

export interface NamedRef {
  id: number
  code: string | null
  name_th: string | null
  name_en: string | null
}

export interface UserRef {
  id: number
  full_name: string
}

export interface TicketListItem {
  id: number
  ticket_number: string
  created_at: string
  last_activity_at: string
  customer_name: string
  contact_name: string
  request_type_code: string
  request_type_name_th: string
  request_type_name_en: string
  subject: string
  priority: Priority
  status: StatusRef
  department: NamedRef
  assigned_user: UserRef | null
  due_at: string | null
  is_overdue: boolean
  is_sample: boolean
}

export interface Page<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface Attachment {
  id: string
  original_filename: string
  mime_type: string
  size_bytes: number
  kind: 'IMAGE' | 'DOCUMENT'
  width: number | null
  height: number | null
  source: 'CUSTOMER' | 'STAFF'
  comment_id: number | null
  uploaded_by_name: string | null
  created_at: string
  url: string
}

export interface HistoryEntry {
  id: number
  created_at: string
  from_status: string | null
  to_status: string
  actor_type: string
  actor_name: string | null
  comment: string | null
}

export interface AssignmentEntry {
  id: number
  created_at: string
  assignment_type: string
  from_department: string | null
  to_department: string
  from_user: string | null
  to_user: string | null
  assigned_by: string | null
  priority: string | null
  due_at: string | null
  reason: string | null
}

export interface CommentEntry {
  id: number
  created_at: string
  author_type: 'STAFF' | 'CUSTOMER' | 'SYSTEM'
  author_name: string | null
  visibility: 'INTERNAL' | 'PUBLIC'
  body: string
}

export interface TransitionOption extends Named {
  to_status: string
  requires_comment: boolean
}

export interface TicketPermissions {
  can_change_status: boolean
  can_assign: boolean
  can_self_assign: boolean
  can_transfer: boolean
  can_comment: boolean
  can_upload: boolean
  can_regenerate_token: boolean
}

export interface TicketDetail {
  id: number
  ticket_number: string
  request_type: NamedRef
  subject: string
  description: string
  category: string | null
  priority: Priority
  status: StatusRef
  source: string
  created_at: string
  updated_at: string
  last_activity_at: string
  due_at: string | null
  first_response_at: string | null
  resolved_at: string | null
  closed_at: string | null
  cancelled_at: string | null
  is_overdue: boolean
  is_sample: boolean
  anonymized_at: string | null
  privacy_consent_version: string | null
  privacy_consent_at: string | null
  customer: { id: number; name: string; customer_type: string; code: string | null }
  contact: { id: number; name: string; department: string | null; phone: string | null; email: string | null }
  department: NamedRef
  assigned_user: UserRef | null
  details: { key: string; label_th: string; label_en: string; value: string | null }[]
  attachments: Attachment[]
  history: HistoryEntry[]
  assignments: AssignmentEntry[]
  comments: CommentEntry[]
  allowed_transitions: TransitionOption[]
  permissions: TicketPermissions
}

export interface TokenResult {
  ticket_number: string
  tracking_token: string
  tracking_url: string
}

// ----------------------------------------------------------------- dashboard / reports

export interface Kpis {
  total: number
  new: number
  open: number
  in_progress: number
  waiting: number
  resolved: number
  closed: number
  cancelled: number
  overdue: number
  sample: number
}

export interface DashboardData {
  kpis: Kpis
  volume_by_month: { month: string; count: number }[]
  by_request_type: (Named & { code: string; count: number })[]
  by_department: (Named & { id: number; count: number })[]
  by_status: (Named & { code: string; color: string; count: number })[]
  by_priority: { priority: Priority; count: number }[]
  resolution_by_request_type: (Named & { code: string; avg_hours: number | null; count: number })[]
  resolution_by_month: { month: string; avg_hours: number | null; count: number }[]
  generated_at: string
}

export interface SummaryReport {
  total: number
  by_request_type: (Named & { code: string; count: number })[]
  by_department: (Named & { id: number; count: number })[]
  by_status: (Named & { code: string; color: string; count: number })[]
  by_month: { month: string; count: number }[]
}

export interface WorkloadRow {
  user_id: number | null
  full_name: string
  role: string
  departments: string[]
  assigned: number
  active: number
  waiting: number
  resolved: number
  closed: number
  overdue: number
}

export interface PerfBlock {
  tickets: number
  responded: number
  resolved: number
  first_response_avg_hours: number | null
  first_response_median_hours: number | null
  first_response_target_met_pct: number | null
  resolution_avg_hours: number | null
  resolution_median_hours: number | null
  resolution_target_met_pct: number | null
  request_type?: string
  priority?: string
}

export interface PerformanceReport {
  overall: PerfBlock
  by_request_type: PerfBlock[]
  by_priority: PerfBlock[]
  open_aging: { bucket: string; count: number }[]
  overdue: {
    id: number
    ticket_number: string
    subject: string
    priority: string
    status_name_th: string
    department: string
    assigned_user: string | null
    due_at: string
    hours_overdue: number
  }[]
  targets: Record<string, { first_response_hours?: number; resolution_hours?: number }>
}

export interface NotificationItem {
  id: number
  event_type: string
  subject: string
  body: string
  ticket_id: number | null
  ticket_number: string | null
  link_url: string | null
  created_at: string
  read_at: string | null
}
