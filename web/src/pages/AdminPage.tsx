import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { admin as adminApi, globalMessages } from '../api/endpoints'
import type { AdminUser, ChatMessage, Note } from '../api/types'
import { useAuth } from '../auth/useAuth'
import { Empty, ErrorNote, Loading, PageHeader } from '../components/ui'
import { formatStamp } from '../lib/format'

type Tab = 'users' | 'notes' | 'chat'

export function AdminPage() {
  const { user } = useAuth()
  const [tab, setTab] = useState<Tab>('users')
  const [users, setUsers] = useState<AdminUser[] | null>(null)
  const [notes, setNotes] = useState<Note[] | null>(null)
  const [lines, setLines] = useState<ChatMessage[] | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    Promise.all([adminApi.users(), adminApi.notes(), globalMessages.list({ limit: 50 })])
      .then(([userList, noteList, messageList]) => {
        setUsers(userList)
        setNotes(noteList)
        setLines(messageList)
        setError(null)
      })
      .catch(setError)
  }, [])

  useEffect(() => {
    load()
  }, [load])

  async function run(action: () => Promise<unknown>, confirmText?: string) {
    if (confirmText && !window.confirm(confirmText)) return
    setBusy(true)
    setError(null)
    try {
      await action()
      load()
    } catch (cause) {
      setError(cause)
    } finally {
      setBusy(false)
    }
  }

  function rename(target: AdminUser) {
    const username = window.prompt('New display name', target.username)
    if (!username || username.trim() === target.username) return
    void run(
      () => adminApi.renameUser(target.id, username.trim()),
      `Rename "${target.username}" to "${username.trim()}"?`,
    )
  }

  if (user?.role !== 'admin') {
    return (
      <div className="page">
        <PageHeader title="Administration" />
        <ErrorNote error={new Error('This page is only available to administrators')} />
        <div>
          <Link className="btn" to="/">
            Back to the dashboard
          </Link>
        </div>
      </div>
    )
  }

  if (!users || !notes || !lines) {
    return (
      <div className="page">
        <Loading label="Loading moderation tools…" />
      </div>
    )
  }

  return (
    <div className="page">
      <PageHeader
        title="Administration"
        subtitle="Rename or remove accounts, take down notes and chat lines"
      />

      <ErrorNote error={error} />

      <div className="row">
        {(['users', 'notes', 'chat'] as Tab[]).map((value) => (
          <button
            key={value}
            type="button"
            className={`btn btn-sm${tab === value ? ' btn-primary' : ''}`}
            onClick={() => setTab(value)}
          >
            {value === 'users' ? 'Accounts' : value === 'notes' ? 'Notes' : 'Global chat'}
          </button>
        ))}
      </div>

      {tab === 'users' ? (
        <section className="card">
          <div className="card-header">
            <h2>Accounts</h2>
            <span className="muted">{users.length}</span>
          </div>
          <div className="card-body" style={{ overflowX: 'auto' }}>
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Phone</th>
                  <th>Role</th>
                  <th>Notes</th>
                  <th>Messages</th>
                  <th>Joined</th>
                  <th aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {users.map((account) => (
                  <tr key={account.id}>
                    <td className="truncate">{account.username}</td>
                    <td>{account.phone}</td>
                    <td>
                      <span className={`badge ${account.role === 'admin' ? 'badge-accent' : ''}`}>
                        {account.role}
                      </span>
                    </td>
                    <td>{account.note_count}</td>
                    <td>{account.message_count}</td>
                    <td>{formatStamp(account.created_at)}</td>
                    <td>
                      <div className="row">
                        <button
                          type="button"
                          className="btn btn-sm"
                          onClick={() => rename(account)}
                          disabled={busy}
                        >
                          Rename
                        </button>
                        <button
                          type="button"
                          className="btn btn-sm btn-danger"
                          onClick={() =>
                            void run(
                              () => adminApi.removeUser(account.id),
                              `Delete "${account.username}" for good? Their notes and files go too.`,
                            )
                          }
                          disabled={busy || account.id === user.id}
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      {tab === 'notes' ? (
        <section className="card">
          <div className="card-header">
            <h2>Notes</h2>
            <span className="muted">{notes.length}</span>
          </div>
          {notes.length === 0 ? (
            <Empty title="No notes yet" />
          ) : (
            <div className="list">
              {notes.map((note) => (
                <div className="list-row" key={note.id}>
                  <span className="truncate">
                    <span className="list-row-title">{note.title}</span>
                    <span className="list-row-sub">
                      {' '}
                      by {note.author} · Semester {note.semester} · {note.branch}
                    </span>
                  </span>
                  <span className="spacer" />
                  <Link className="btn btn-sm" to={`/notes/${note.id}`}>
                    Open
                  </Link>
                  <button
                    type="button"
                    className="btn btn-sm btn-danger"
                    onClick={() =>
                      void run(
                        () => adminApi.removeNote(note.id),
                        `Delete "${note.title}" for everyone?`,
                      )
                    }
                    disabled={busy}
                  >
                    Delete
                  </button>
                </div>
              ))}
            </div>
          )}
        </section>
      ) : null}

      {tab === 'chat' ? (
        <section className="card">
          <div className="card-header">
            <h2>Recent global chat</h2>
            <span className="muted">{lines.length}</span>
          </div>
          {lines.length === 0 ? (
            <Empty title="No messages yet" />
          ) : (
            <div className="list">
              {lines.map((line) => (
                <div className="list-row" key={line.id}>
                  <span className="truncate">
                    <span className="list-row-title">{line.sender}</span>
                    <span className="list-row-sub"> {line.body}</span>
                  </span>
                  <span className="spacer" />
                  <span className="list-row-sub">{formatStamp(line.created_at)}</span>
                  <button
                    type="button"
                    className="btn btn-sm btn-danger"
                    onClick={() =>
                      void run(
                        () => adminApi.removeGlobalMessage(line.id),
                        'Delete this line for everyone?',
                      )
                    }
                    disabled={busy}
                  >
                    Delete
                  </button>
                </div>
              ))}
            </div>
          )}
        </section>
      ) : null}
    </div>
  )
}
