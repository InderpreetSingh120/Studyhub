import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { globalChatSocketUrl, globalMessages as globalApi } from '../api/endpoints'
import type { ChatMessage, ServerFrame } from '../api/types'
import { useAuth } from '../auth/useAuth'
import { Empty, ErrorNote, Loading, PageHeader } from '../components/ui'
import { errorMessage, formatStamp } from '../lib/format'

type SocketStatus = 'connecting' | 'online' | 'offline'

const HISTORY_PAGE = 50

export function ChatPage() {
  const { logout, user } = useAuth()

  const [messages, setMessages] = useState<ChatMessage[] | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [socketError, setSocketError] = useState<string | null>(null)
  const [status, setStatus] = useState<SocketStatus>('connecting')
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false)
  const [attempt, setAttempt] = useState(0)

  const socketRef = useRef<WebSocket | null>(null)
  const scrollRef = useRef<HTMLDivElement | null>(null)

  const appendMessage = useCallback((incoming: ChatMessage) => {
    setMessages((current) => {
      if (!current) return [incoming]
      return current.some((message) => message.id === incoming.id)
        ? current
        : [...current, incoming]
    })
  }, [])

  useEffect(() => {
    let cancelled = false
    globalApi
      .list({ limit: HISTORY_PAGE })
      .then((history) => {
        if (cancelled) return
        setMessages(history)
        setError(null)
      })
      .catch((cause) => {
        if (!cancelled) setError(cause)
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    const socket = new WebSocket(globalChatSocketUrl())
    socketRef.current = socket

    socket.onopen = () => setStatus('online')

    socket.onmessage = (event) => {
      let frame: ServerFrame
      try {
        frame = JSON.parse(String(event.data)) as ServerFrame
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
      if (event.code === 4401) logout()
    }

    return () => {
      socket.close()
      socketRef.current = null
    }
  }, [attempt, appendMessage, logout])

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
      appendMessage(await globalApi.post(body))
    } catch (cause) {
      setSocketError(errorMessage(cause))
    }
  }

  async function loadOlder() {
    const oldest = messages?.[0]
    if (!oldest) return
    setBusy(true)
    try {
      const older = await globalApi.list({
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

  if (error && !messages) {
    return (
      <div className="page">
        <PageHeader title="Everyone's chat" />
        <ErrorNote error={error} />
        <div>
          <button
            type="button"
            className="btn"
            onClick={() => {
              setError(null)
              setAttempt((value) => value + 1)
            }}
          >
            Try again
          </button>
        </div>
      </div>
    )
  }

  if (messages === null) {
    return (
      <div className="page">
        <Loading label="Opening the chat…" />
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
        title="Everyone's chat"
        subtitle="One room for the whole campus — groups stay private"
        actions={
          status === 'offline' ? (
            <button
              type="button"
              className="btn"
              onClick={() => {
                setStatus('connecting')
                setSocketError(null)
                setAttempt((value) => value + 1)
              }}
            >
              Reconnect
            </button>
          ) : null
        }
      />

      <ErrorNote error={error} />
      {socketError ? <div className="alert alert-warning">{socketError}</div> : null}

      <section className="card chat">
        <div className="chat-head">
          <h2>Global chat</h2>
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
              Say hello — everyone signed in will see it live.
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
                ? 'Write a message to everyone…'
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
    </div>
  )
}
