/** Response shapes mirroring docs/api.md — the contract both clients share. */

export interface User {
  id: number
  username: string
  phone: string
  role: UserRole
  created_at: string
}

export type UserRole = 'admin' | 'user'
export type MembershipRole = 'owner' | 'member'

export interface TokenResponse {
  access_token: string
  token_type: string
  user: User
}

export interface Health {
  status: string
  database: string
  environment: string
  version: string
}

export interface Subject {
  id: number
  name: string
  color: string | null
  created_by: number | null
  created_at: string
}

export type NoteKind = 'notes' | 'practical' | 'mst' | 'final'

export const NOTE_KINDS: NoteKind[] = ['notes', 'practical', 'mst', 'final']

export const KIND_LABELS: Record<NoteKind, string> = {
  notes: 'Notes',
  practical: 'Practical',
  mst: 'MST',
  final: 'Finals',
}

export const BRANCHES = ['CSE', 'IT', 'ECE', 'EEE', 'MECH', 'CIVIL']

export interface Note {
  id: number
  title: string
  body: string
  subject_id: number | null
  semester: number
  branch: string
  kind: NoteKind
  kind_label: string
  is_done: boolean
  author_id: number
  author: string
  attachment_count: number
  created_at: string
  updated_at: string
}

export type SummaryStatus = 'pending' | 'ready' | 'failed' | 'skipped'

export interface Attachment {
  id: number
  filename: string
  content_type: string
  size_bytes: number
  summary: string | null
  summary_status: SummaryStatus
  created_at: string
}

export interface Group {
  id: number
  name: string
  description: string
  invite_code: string
  created_at: string
  member_count: number
  my_role: MembershipRole
}

export interface GroupMember {
  user_id: number
  username: string
  role: MembershipRole
  joined_at: string
}

/** Shared by the group rooms and the everyone-chat (no `group_id` there). */
export interface ChatMessage {
  id: number
  sender_id: number
  sender: string
  body: string
  created_at: string
}

export interface Message extends ChatMessage {
  group_id: number
}

export interface SubjectCount {
  subject_id: number
  name: string
  color: string | null
  count: number
}

export interface LabelCount {
  key: string
  label: string
  count: number
}

export interface DashboardNote {
  id: number
  title: string
  author: string
  subject_id: number | null
  semester: number
  branch: string
  kind: NoteKind
  is_done: boolean
  updated_at: string
}

export interface MessagePreview {
  sender: string
  body: string
  created_at: string
}

export interface DashboardGroup {
  id: number
  name: string
  member_count: number
  last_message: MessagePreview | null
}

export interface TrendPoint {
  date: string
  count: number
}

export interface Dashboard {
  notes: {
    total: number
    done: number
    without_subject: number
    by_subject: SubjectCount[]
    by_kind: LabelCount[]
    by_branch: LabelCount[]
    by_semester: LabelCount[]
  }
  recent_notes: DashboardNote[]
  groups: DashboardGroup[]
  trend: TrendPoint[]
}

export interface AdminUser {
  id: number
  username: string
  phone: string
  role: UserRole
  created_at: string
  note_count: number
  message_count: number
}

export type ServerFrame<T extends ChatMessage = ChatMessage> =
  | { type: 'connected'; group_id: number; user_id: number }
  | { type: 'message'; message: T }
  | { type: 'pong' }
  | { type: 'error'; detail: string }
