import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  chatSocketUrl,
  groups as groupsApi,
  messages as messagesApi,
} from '../api/endpoints'
import type { Group, GroupMember, Message, ServerFrame } from '../api/types'
import { useAuth } from '../auth/useAuth'
import { Empty, ErrorNote, Loading, PageHeader } from '../components/ui'
import { errorMessage, formatStamp } from '../lib/format'
type SocketStatus = 'connecting' | 'online' | 'offline'

const HISTORY_PAGE = 50

export function GroupPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { logout, user } = useAuth()
  const groupId = Number(id)

  const [group, setGroup] = useState<Group | null>(null)
  const [members, setMembers] = useState<GroupMember[] | null>(null)
  const [messages, setMessages] = useState<Message[] | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [socketError, setSocketError] = useState<string | null>(null)
  const [status, setStatus] = useState<SocketStatus>('connecting')
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false)
  const [attempt, setAttempt] = useState(0)

  const socketRef = useRef<WebSocket | null>(null)
  const scrollRef = useRef<HTMLDivElement | null>(null)

  const appendMessage = useCallback((incoming: Message) => {
    setMessages((current) => {
      if (!current) return [incoming]
      return current.some((message) => message.id === incoming.id)
        ? current
        : [...current, incoming]
    })
  }, [])

  useEffect(() => {
    let cancelled = false
    Promise.all([
      groupsApi.get(groupId),
      groupsApi.members(groupId),
      messagesApi.list(groupId, { limit: HISTORY_PAGE }),
    ])
      .then(([loadedGroup, loadedMembers, history]) => {
        if (cancelled) return
        setGroup(loadedGroup)
        setMembers(loadedMembers)
        setMessages(history)
        setError(null)
      })
      .catch((cause) => {
        if (!cancelled) setError(cause)
      })
    return () => {
      cancelled = true
    }
  }, [groupId])

  useEffect(() => {
    if (!group) return
    const socket = new WebSocket(chatSocketUrl(groupId))
    socketRef.current = socket

    socket.onopen = () => setStatus('online')

    socket.onmessage = (event) => {
      let frame: ServerFrame<Message>
      try {
        frame = JSON.parse(String(event.data)) as ServerFrame<Message>
      } catch {
        return
      }
      if (frame.type === 'message') appendMessage(frame.message)
      else if (frame.type === 'error') setSocketError(frame.detail)
      else if (frame.type === 'connected') setStatus('online')
    }

    socket.onerror = () => setStatus('offline')

    socket.onclose = (event) => {
      setStatus('offline')
      socketRef.current = null
      if (event.code === 4401) {
        logout()
        navigate('/login', { replace: true })
      } else if (event.code === 4404) {
        setError(new Error('You are not a member of this group any more'))
      }
    }

    return () => {
      socket.close()
      socketRef.current = null
    }
  }, [group, groupId, attempt, appendMessage, logout, navigate])

  useEffect(() => {
    const container = scrollRef.current
    if (container) container.scrollTop = container.scrollHeight
  }, [messages])

  async function handleSend(event: FormEvent) {
    event.preventDefault()
    const body = draft.trim()
    if (!body) return
    setDraft('')
    setSocketError(null)

    const socket = socketRef.current
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: 'message', body }))
      return
    }
    try {
      appendMessage(await messagesApi.post(groupId, body))
    } catch (cause) {
      setSocketError(errorMessage(cause))
    }
  }

  async function loadOlder() {
    const oldest = messages?.[0]
    if (!oldest) return
    setBusy(true)
    try {
      const older = await messagesApi.list(groupId, {
        before_id: oldest.id,
        limit: HISTORY_PAGE,
      })
      setMessages((current) => [...older, ...(current ?? [])])
    } catch (cause) {
      setError(cause)
    } finally {
      setBusy(false)
    }
  }

  async function handleLeave() {
    if (!group || !window.confirm(`Leave "${group.name}"?`)) return
    setBusy(true)
    try {
      await groupsApi.leave(groupId)
      navigate('/groups', { replace: true })
    } catch (cause) {
      setError(cause)
      setBusy(false)
    }
  }

  async function handleDelete() {
    if (!group || !window.confirm(`Delete "${group.name}" for everyone?`)) return
    setBusy(true)
    try {
      await groupsApi.remove(groupId)
      navigate('/groups', { replace: true })
    } catch (cause) {
      setError(cause)
      setBusy(false)
    }
  }

  async function copyCode() {
    if (!group) return
    try {
      await navigator.clipboard.writeText(group.invite_code)
      setSocketError(null)
    } catch {
      setSocketError(`Invite code: ${group.invite_code}`)
    }
  }

  if (!group && error) {
    return (
      <div className="page">
        <PageHeader title="Group" />
        <ErrorNote error={error} />
        <div>
          <Link className="btn" to="/groups">
            Back to groups
          </Link>
        </div>
      </div>
    )
  }

  if (!group || !members || messages === null) {
    return (
      <div className="page">
        <Loading label="Opening the group…" />
      </div>
    )
  }

  const statusLabel =
    status === 'online'
      ? 'Live'
      : status === 'connecting'
        ? 'Connecting…'
        : 'Offline'

  return (
    <div className="page">
      <PageHeader
        title={group.name}
        subtitle={group.description || undefined}
        actions={
          <>
            <Link className="btn btn-ghost" to="/groups">
              All groups
            </Link>
            <button
              type="button"
              className="btn"
              onClick={handleLeave}
              disabled={busy}
            >
              Leave
            </button>
            {group.my_role === 'owner' ? (
              <button
                type="button"
                className="btn btn-danger"
                onClick={handleDelete}
                disabled={busy}
              >
                Delete group
              </button>
            ) : null}
          </>
        }
      />

      <ErrorNote error={error} />
      {socketError ? <div className="alert alert-warning">{socketError}</div> : null}

      <div className="row">
        <span className={`badge ${group.my_role === 'owner' ? 'badge-accent' : ''}`}>
          {group.my_role}
        </span>
        <span className="badge">
          {group.member_count} member{group.member_count === 1 ? '' : 's'}
        </span>
        <button type="button" className="btn btn-sm" onClick={() => void copyCode()}>
          Copy invite code
        </button>
        <code>{group.invite_code}</code>
        {status === 'offline' ? (
          <button
            type="button"
            className="btn btn-sm"
            onClick={() => {
              setStatus('connecting')
              setSocketError(null)
              setAttempt((value) => value + 1)
            }}
          >
            Reconnect
          </button>
        ) : null}
      </div>

      <section className="card chat">
        <div className="chat-head">
          <h2>Chat</h2>
          <span className="spacer" />
          <span className="composer-status">
            <span
              className={`status-dot ${
                status === 'online'
                  ? 'is-online'
                  : status === 'offline'
                    ? 'is-offline'
                    : ''
              }`}
            />
            {statusLabel}
          </span>
        </div>

        <div className="messages" ref={scrollRef}>
          {messages.length >= HISTORY_PAGE ? (
            <div style={{ textAlign: 'center' }}>
              <button
                type="button"
                className="btn btn-sm"
                onClick={() => void loadOlder()}
                disabled={busy}
              >
                Load earlier messages
              </button>
            </div>
          ) : null}

          {messages.length === 0 ? (
            <Empty title="No messages yet">
              Say hello — everyone in {group.name} will see it live.
            </Empty>
          ) : (
            messages.map((message) => {
              const mine = message.sender_id === user?.id
              return (
                <article
                  className={`message${mine ? ' message--mine' : ''}`}
                  key={message.id}
                >
                  <div className="message-body">
                    <div className="message-meta">
                      <span className="message-author">{message.sender}</span>
                      <span className="message-time">
                        {formatStamp(message.created_at)}
                      </span>
                    </div>
                    <div className="message-text">{message.body}</div>
                  </div>
                </article>
              )
            })
          )}
        </div>

        <form className="composer" onSubmit={handleSend}>
          <input
            className="input"
            placeholder={
              status === 'online'
                ? 'Write a message…'
                : 'Reconnecting — messages can still be sent'
            }
            maxLength={4000}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            aria-label="Message"
          />
          <button
            type="submit"
            className="btn btn-primary"
            disabled={draft.trim().length === 0}
          >
            Send
          </button>
        </form>
      </section>

      <section className="card">
        <div className="card-header">
          <h2>Members</h2>
          <span className="muted">{members.length}</span>
        </div>
        <div className="member-list">
          {members.map((member) => (
            <div className="list-row" key={member.user_id}>
              <span className="avatar">{member.username.slice(0, 2)}</span>
              <span className="list-row-title truncate">{member.username}</span>
              <span className="spacer" />
              <span className={`badge ${member.role === 'owner' ? 'badge-accent' : ''}`}>
                {member.role}
              </span>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
