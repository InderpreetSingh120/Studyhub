/** One function per endpoint of docs/api.md; the pages never call fetch directly. */

import { apiRequest, getAuthToken } from './http'
import type {
  AdminUser,
  Attachment,
  ChatMessage,
  Dashboard,
  Group,
  GroupMember,
  Message,
  Note,
  NoteKind,
  Subject,
  TokenResponse,
  User,
} from './types'

type Query = Record<string, string | number | boolean | undefined>

function query(params: Query): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') search.set(key, String(value))
  }
  const text = search.toString()
  return text ? `?${text}` : ''
}

export interface RegisterInput {
  username: string
  phone: string
  password: string
}

export interface LoginInput {
  /** Phone number, or a username when nobody else shares it. */
  identifier: string
  password: string
}

export const auth = {
  register: (input: RegisterInput) =>
    apiRequest<TokenResponse>('/auth/register', {
      method: 'POST',
      body: input,
      auth: false,
    }),
  login: (input: LoginInput) =>
    apiRequest<TokenResponse>('/auth/login', {
      method: 'POST',
      body: input,
      auth: false,
    }),
  me: () => apiRequest<User>('/auth/me'),
}

export const subjects = {
  list: () => apiRequest<Subject[]>('/subjects'),
  create: (input: { name: string; color?: string | null }) =>
    apiRequest<Subject>('/subjects', { method: 'POST', body: input }),
  update: (id: number, input: { name?: string; color?: string | null }) =>
    apiRequest<Subject>(`/subjects/${id}`, { method: 'PATCH', body: input }),
  remove: (id: number) =>
    apiRequest<void>(`/subjects/${id}`, { method: 'DELETE' }),
}

export interface NoteInput {
  title: string
  body?: string
  subject_id?: number | null
  semester: number
  branch: string
  kind?: NoteKind
  is_done?: boolean
}

export interface NoteFilters {
  q?: string
  subject_id?: number
  semester?: number
  branch?: string
  kind?: NoteKind
  mine?: boolean
  done?: boolean
  limit?: number
  offset?: number
}

export const notes = {
  list: (filters: NoteFilters = {}) =>
    apiRequest<Note[]>(`/notes${query(filters as Query)}`),
  get: (id: number) => apiRequest<Note>(`/notes/${id}`),
  create: (input: NoteInput) =>
    apiRequest<Note>('/notes', { method: 'POST', body: input }),
  update: (id: number, input: Partial<NoteInput>) =>
    apiRequest<Note>(`/notes/${id}`, { method: 'PATCH', body: input }),
  remove: (id: number) => apiRequest<void>(`/notes/${id}`, { method: 'DELETE' }),
}

export const attachments = {
  list: (noteId: number) =>
    apiRequest<Attachment[]>(`/notes/${noteId}/attachments`),
  upload: (noteId: number, file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return apiRequest<Attachment>(`/notes/${noteId}/attachments`, {
      method: 'POST',
      formData,
    })
  },
  remove: (noteId: number, attachmentId: number) =>
    apiRequest<void>(`/notes/${noteId}/attachments/${attachmentId}`, {
      method: 'DELETE',
    }),
}

/** Attachments need the bearer header, so they are fetched and saved locally
 * instead of being opened as a plain link. */
export async function downloadAttachment(noteId: number, attachment: Attachment): Promise<void> {
  const response = await fetch(
    `/api/notes/${noteId}/attachments/${attachment.id}`,
    { headers: { Authorization: `Bearer ${getAuthToken() ?? ''}` } },
  )
  if (!response.ok) throw new Error(`Download failed (${response.status})`)
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = attachment.filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

/** Browser view for an attachment: a blob URL the viewer opens in a tab. */
export async function openAttachment(noteId: number, attachment: Attachment): Promise<string> {
  const response = await fetch(
    `/api/notes/${noteId}/attachments/${attachment.id}`,
    { headers: { Authorization: `Bearer ${getAuthToken() ?? ''}` } },
  )
  if (!response.ok) throw new Error(`Could not open the file (${response.status})`)
  return URL.createObjectURL(await response.blob())
}

export interface GroupInput {
  name: string
  description?: string
}

export const groups = {
  list: () => apiRequest<Group[]>('/groups'),
  get: (id: number) => apiRequest<Group>(`/groups/${id}`),
  create: (input: GroupInput) =>
    apiRequest<Group>('/groups', { method: 'POST', body: input }),
  join: (inviteCode: string) =>
    apiRequest<Group>('/groups/join', {
      method: 'POST',
      body: { invite_code: inviteCode },
    }),
  members: (id: number) => apiRequest<GroupMember[]>(`/groups/${id}/members`),
  update: (id: number, input: GroupInput) =>
    apiRequest<Group>(`/groups/${id}`, { method: 'PATCH', body: input }),
  leave: (id: number) =>
    apiRequest<void>(`/groups/${id}/leave`, { method: 'POST' }),
  remove: (id: number) => apiRequest<void>(`/groups/${id}`, { method: 'DELETE' }),
}

export const messages = {
  list: (groupId: number, params: { before_id?: number; limit?: number } = {}) =>
    apiRequest<Message[]>(`/groups/${groupId}/messages${query(params)}`),
  post: (groupId: number, body: string) =>
    apiRequest<Message>(`/groups/${groupId}/messages`, {
      method: 'POST',
      body: { body },
    }),
}

export const globalMessages = {
  list: (params: { before_id?: number; limit?: number } = {}) =>
    apiRequest<ChatMessage[]>(`/chat${query(params)}`),
  post: (body: string) =>
    apiRequest<ChatMessage>('/chat', { method: 'POST', body: { body } }),
}

export const dashboard = {
  get: () => apiRequest<Dashboard>('/dashboard'),
}

export const admin = {
  users: () => apiRequest<AdminUser[]>('/admin/users'),
  renameUser: (id: number, username: string) =>
    apiRequest<User>(`/admin/users/${id}`, {
      method: 'PATCH',
      body: { username },
    }),
  removeUser: (id: number) =>
    apiRequest<void>(`/admin/users/${id}`, { method: 'DELETE' }),
  notes: () => apiRequest<Note[]>('/admin/notes'),
  removeNote: (id: number) =>
    apiRequest<void>(`/admin/notes/${id}`, { method: 'DELETE' }),
  removeGlobalMessage: (id: number) =>
    apiRequest<void>(`/admin/chat/messages/${id}`, { method: 'DELETE' }),
  removeGroupMessage: (groupId: number, id: number) =>
    apiRequest<void>(`/admin/groups/${groupId}/messages/${id}`, {
      method: 'DELETE',
    }),
}

function socketUrl(path: string): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const token = encodeURIComponent(getAuthToken() ?? '')
  return `${protocol}//${window.location.host}${path}?token=${token}`
}

export function chatSocketUrl(groupId: number): string {
  return socketUrl(`/api/ws/groups/${groupId}`)
}

export function globalChatSocketUrl(): string {
  return socketUrl('/api/ws/global')
}
