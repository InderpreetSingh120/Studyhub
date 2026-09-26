import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { groups as groupsApi } from '../api/endpoints'
import type { Group } from '../api/types'
import { Empty, ErrorNote, Loading, PageHeader } from '../components/ui'

export function GroupsPage() {
  const [groups, setGroups] = useState<Group[] | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const [showCreate, setShowCreate] = useState(false)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [inviteCode, setInviteCode] = useState('')

  const load = useCallback(() => {
    groupsApi
      .list()
      .then(setGroups)
      .catch(setError)
  }, [])

  useEffect(() => {
    load()
  }, [load])

  async function handleCreate(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      const created = await groupsApi.create({ name, description })
      setName('')
      setDescription('')
      setShowCreate(false)
      setNotice(`"${created.name}" is ready — invite friends with ${created.invite_code}`)
      load()
    } catch (cause) {
      setError(cause)
    } finally {
      setBusy(false)
    }
  }

  async function handleJoin(event: FormEvent) {
    event.preventDefault()
    if (!inviteCode.trim()) return
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      const joined = await groupsApi.join(inviteCode.trim())
      setInviteCode('')
      setNotice(`Joined "${joined.name}"`)
      load()
    } catch (cause) {
      setError(cause)
    } finally {
      setBusy(false)
    }
  }

  async function copyCode(group: Group) {
    try {
      await navigator.clipboard.writeText(group.invite_code)
      setNotice(`Invite code for ${group.name}: ${group.invite_code} copied`)
    } catch {
      setNotice(`Invite code for ${group.name}: ${group.invite_code}`)
    }
  }

  if (!groups) {
    return (
      <div className="page">
        {error ? <ErrorNote error={error} /> : <Loading label="Loading your groups…" />}
      </div>
    )
  }

  return (
    <div className="page">
      <PageHeader
        title="Groups"
        subtitle="Private study groups you share notes and chat with"
        actions={
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => setShowCreate((visible) => !visible)}
          >
            {showCreate ? 'Cancel' : 'New group'}
          </button>
        }
      />

      <ErrorNote error={error} />
      {notice ? <div className="alert alert-info">{notice}</div> : null}

      {showCreate ? (
        <form className="card" onSubmit={handleCreate}>
          <div className="card-header">
            <h2>Create a group</h2>
          </div>
          <div className="card-body stack">
            <div className="field">
              <label htmlFor="group-name">Name</label>
              <input
                id="group-name"
                className="input"
                maxLength={60}
                placeholder="Exam prep"
                required
                value={name}
                onChange={(event) => setName(event.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="group-description">Description</label>
              <input
                id="group-description"
                className="input"
                maxLength={200}
                placeholder="Week 12, Tuesdays"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
              />
            </div>
            <div className="row">
              <button
                type="submit"
                className="btn btn-primary"
                disabled={busy || name.trim().length === 0}
              >
                {busy ? 'Creating…' : 'Create group'}
              </button>
            </div>
          </div>
        </form>
      ) : null}

      <form className="card" onSubmit={handleJoin}>
        <div className="card-body row" style={{ flexWrap: 'nowrap' }}>
          <div className="field" style={{ flex: 1 }}>
            <label htmlFor="join-code">Join with an invite code</label>
            <input
              id="join-code"
              className="input"
              placeholder="C74GSXWS"
              value={inviteCode}
              onChange={(event) => setInviteCode(event.target.value.toUpperCase())}
            />
          </div>
          <button
            type="submit"
            className="btn"
            disabled={busy || inviteCode.trim().length === 0}
            style={{ marginTop: 22 }}
          >
            Join
          </button>
        </div>
      </form>

      {groups.length === 0 ? (
        <Empty title="You are not in any group yet">
          Create one and share the invite code, or paste a code you were given.
        </Empty>
      ) : (
        <div className="group-grid">
          {groups.map((group) => (
            <section className="card group-card" key={group.id}>
              <div className="row-between">
                <h3 className="truncate">
                  <Link to={`/groups/${group.id}`}>{group.name}</Link>
                </h3>
                <span className={`badge ${group.my_role === 'owner' ? 'badge-accent' : ''}`}>
                  {group.my_role}
                </span>
              </div>
              {group.description ? (
                <p className="muted truncate">{group.description}</p>
              ) : (
                <p className="faint">No description</p>
              )}
              <div className="row">
                <span className="badge">
                  {group.member_count} member{group.member_count === 1 ? '' : 's'}
                </span>
                <button
                  type="button"
                  className="btn btn-sm"
                  onClick={() => void copyCode(group)}
                >
                  Copy code
                </button>
              </div>
              <code>{group.invite_code}</code>
              <Link className="btn btn-block" to={`/groups/${group.id}`}>
                Open chat
              </Link>
            </section>
          ))}
        </div>
      )}
    </div>
  )
}
