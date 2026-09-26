import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { dashboard, notes as notesApi, subjects as subjectsApi } from '../api/endpoints'
import { BRANCHES, KIND_LABELS, NOTE_KINDS, type Note, type NoteKind, type Subject, type SubjectCount } from '../api/types'
import { useAuth } from '../auth/useAuth'
import { Empty, ErrorNote, Loading, PageHeader } from '../components/ui'
import { formatStamp } from '../lib/format'

const SEMESTERS = [1, 2, 3, 4, 5, 6, 7, 8]

export function NotesPage() {
  const { user } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()

  const subjectParam = searchParams.get('subject')
  const subjectId = subjectParam ? Number(subjectParam) : null
  const query = searchParams.get('q') ?? ''
  const semester = searchParams.get('semester') ?? ''
  const branch = searchParams.get('branch') ?? ''
  const kind = searchParams.get('kind') ?? ''
  const mine = searchParams.get('mine') === '1'
  const done = searchParams.get('done') ?? ''

  const [subjects, setSubjects] = useState<Subject[] | null>(null)
  const [counts, setCounts] = useState<SubjectCount[]>([])
  const [notes, setNotes] = useState<Note[] | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [newName, setNewName] = useState('')
  const [newColor, setNewColor] = useState('#3b82f6')
  const [busy, setBusy] = useState(false)

  const activeSubject = subjects?.find((subject) => subject.id === subjectId) ?? null
  const canEditSubject = (subject: Subject) =>
    user?.role === 'admin' || subject.created_by === user?.id

  const loadSubjects = useCallback(() => {
    Promise.all([subjectsApi.list(), dashboard.get()])
      .then(([list, summary]) => {
        setSubjects(list)
        setCounts(summary.notes.by_subject)
      })
      .catch(setError)
  }, [])

  useEffect(() => {
    loadSubjects()
  }, [loadSubjects])

  useEffect(() => {
    let cancelled = false
    notesApi
      .list({
        q: query || undefined,
        subject_id: subjectId ?? undefined,
        semester: semester ? Number(semester) : undefined,
        branch: branch || undefined,
        kind: (kind || undefined) as NoteKind | undefined,
        mine: mine || undefined,
        done: done ? done === 'true' : undefined,
        limit: 200,
      })
      .then((list) => {
        if (cancelled) return
        setNotes(list)
        setError(null)
      })
      .catch((cause) => {
        if (!cancelled) setError(cause)
      })
    return () => {
      cancelled = true
    }
  }, [query, subjectId, semester, branch, kind, mine, done])

  function updateParams(patch: Record<string, string | null>) {
    const next = new URLSearchParams(searchParams)
    for (const [key, value] of Object.entries(patch)) {
      if (value === null || value === '') next.delete(key)
      else next.set(key, value)
    }
    setSearchParams(next, { replace: true })
  }

  async function handleCreateSubject(event: FormEvent) {
    event.preventDefault()
    const name = newName.trim()
    if (!name) return
    setBusy(true)
    setError(null)
    try {
      const subject = await subjectsApi.create({ name, color: newColor })
      setNewName('')
      loadSubjects()
      updateParams({ subject: String(subject.id) })
    } catch (cause) {
      setError(cause)
    } finally {
      setBusy(false)
    }
  }

  async function handleRenameSubject() {
    if (!activeSubject) return
    const name = window.prompt('Rename subject', activeSubject.name)
    if (!name || name.trim() === activeSubject.name) return
    setBusy(true)
    setError(null)
    try {
      await subjectsApi.update(activeSubject.id, { name: name.trim() })
      loadSubjects()
    } catch (cause) {
      setError(cause)
    } finally {
      setBusy(false)
    }
  }

  async function handleDeleteSubject() {
    if (!activeSubject) return
    const count = counts.find((item) => item.subject_id === activeSubject.id)?.count ?? 0
    const warning = count
      ? `Delete "${activeSubject.name}"? Its ${count} note(s) will lose their subject.`
      : `Delete "${activeSubject.name}"?`
    if (!window.confirm(warning)) return
    setBusy(true)
    setError(null)
    try {
      await subjectsApi.remove(activeSubject.id)
      updateParams({ subject: null })
      loadSubjects()
    } catch (cause) {
      setError(cause)
    } finally {
      setBusy(false)
    }
  }

  if (error && !subjects) {
    return (
      <div className="page">
        <PageHeader title="Notes gallery" />
        <ErrorNote error={error} />
      </div>
    )
  }

  if (!subjects || !notes) {
    return (
      <div className="page">
        <Loading label="Loading the gallery…" />
      </div>
    )
  }

  const subjectName = (id: number | null) =>
    id === null ? null : (subjects.find((subject) => subject.id === id)?.name ?? null)
  const hasFilters = Boolean(query || semester || branch || kind || mine || done || subjectId)

  return (
    <div className="page">
      <PageHeader
        title="Notes gallery"
        subtitle="Everyone's notes, newest first — pick one to read and download"
        actions={
          <Link className="btn btn-primary" to="/notes/new">
            Upload a note
          </Link>
        }
      />

      <ErrorNote error={error} />

      <div className="notes-layout">
        <section className="card">
          <div className="card-header">
            <h2>Subjects</h2>
          </div>
          <div className="subject-list">
            <button
              type="button"
              className={`subject-item${subjectId === null ? ' is-active' : ''}`}
              onClick={() => updateParams({ subject: null })}
            >
              All subjects
              <span className="subject-count">
                {counts.reduce((sum, item) => sum + item.count, 0) || ''}
              </span>
            </button>

            {subjects.map((subject) => (
              <button
                type="button"
                key={subject.id}
                className={`subject-item${subjectId === subject.id ? ' is-active' : ''}`}
                onClick={() => updateParams({ subject: String(subject.id) })}
              >
                <span
                  className="dot"
                  style={{ background: subject.color ?? 'var(--accent)' }}
                />
                <span className="truncate">{subject.name}</span>
                <span className="subject-count">
                  {counts.find((item) => item.subject_id === subject.id)?.count ?? 0}
                </span>
              </button>
            ))}

            {subjects.length === 0 ? (
              <p className="hint" style={{ padding: '0 10px' }}>
                No subjects yet — add the first one below.
              </p>
            ) : null}
          </div>

          <div className="card-body stack stack-sm" style={{ borderTop: '1px solid var(--border)' }}>
            {activeSubject && canEditSubject(activeSubject) ? (
              <div className="row">
                <button
                  type="button"
                  className="btn btn-sm"
                  onClick={handleRenameSubject}
                  disabled={busy}
                >
                  Rename
                </button>
                <button
                  type="button"
                  className="btn btn-sm btn-danger"
                  onClick={handleDeleteSubject}
                  disabled={busy}
                >
                  Delete
                </button>
              </div>
            ) : null}

            <form className="stack stack-sm" onSubmit={handleCreateSubject}>
              <div className="field">
                <label htmlFor="new-subject">New subject</label>
                <div className="row" style={{ flexWrap: 'nowrap' }}>
                  <input
                    id="new-subject"
                    className="input"
                    placeholder="Linear algebra"
                    maxLength={60}
                    value={newName}
                    onChange={(event) => setNewName(event.target.value)}
                  />
                  <input
                    type="color"
                    className="input"
                    style={{ width: 44, padding: 4 }}
                    value={newColor}
                    onChange={(event) => setNewColor(event.target.value)}
                    title="Subject colour"
                    aria-label="Subject colour"
                  />
                </div>
              </div>
              <button
                type="submit"
                className="btn btn-sm"
                disabled={busy || newName.trim().length === 0}
              >
                Add subject
              </button>
            </form>
          </div>
        </section>

        <section className="card">
          <div className="card-header">
            <h2>{activeSubject ? activeSubject.name : 'All notes'}</h2>
            <div className="row">
              {mine ? <span className="badge badge-accent">Only mine</span> : null}
              <span className="muted">
                {notes.length} note{notes.length === 1 ? '' : 's'}
              </span>
            </div>
          </div>

          <div className="card-body" style={{ paddingBottom: 0 }}>
            <div className="toolbar">
              <input
                className="input"
                type="search"
                placeholder="Search title, body or author…"
                value={query}
                onChange={(event) => updateParams({ q: event.target.value })}
              />
              <select
                className="select"
                style={{ width: 'auto' }}
                value={semester}
                onChange={(event) => updateParams({ semester: event.target.value })}
                aria-label="Filter by semester"
              >
                <option value="">Any semester</option>
                {SEMESTERS.map((value) => (
                  <option key={value} value={value}>
                    Semester {value}
                  </option>
                ))}
              </select>
              <select
                className="select"
                style={{ width: 'auto' }}
                value={branch}
                onChange={(event) => updateParams({ branch: event.target.value })}
                aria-label="Filter by branch"
              >
                <option value="">Any branch</option>
                {BRANCHES.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
              <select
                className="select"
                style={{ width: 'auto' }}
                value={kind}
                onChange={(event) => updateParams({ kind: event.target.value })}
                aria-label="Filter by type"
              >
                <option value="">Any type</option>
                {NOTE_KINDS.map((value) => (
                  <option key={value} value={value}>
                    {KIND_LABELS[value]}
                  </option>
                ))}
              </select>
              <select
                className="select"
                style={{ width: 'auto' }}
                value={done}
                onChange={(event) => updateParams({ done: event.target.value })}
                aria-label="Filter by completion"
              >
                <option value="">Any status</option>
                <option value="false">Open</option>
                <option value="true">Completed</option>
              </select>
              <button
                type="button"
                className={`btn btn-sm${mine ? ' btn-primary' : ''}`}
                onClick={() => updateParams({ mine: mine ? null : '1' })}
              >
                {mine ? 'Showing mine' : 'Only my notes'}
              </button>
              {hasFilters ? (
                <button
                  type="button"
                  className="btn btn-sm btn-ghost"
                  onClick={() => setSearchParams({}, { replace: true })}
                >
                  Clear
                </button>
              ) : null}
            </div>
          </div>

          {notes.length === 0 ? (
            <Empty
              title={hasFilters ? 'No matching notes' : 'No notes yet'}
              action={
                <Link className="btn btn-primary btn-sm" to="/notes/new">
                  Upload a note
                </Link>
              }
            >
              {hasFilters
                ? 'Try a different search or clear the filters.'
                : 'Be the first to share notes with everyone.'}
            </Empty>
          ) : (
            <div className="list">
              {notes.map((note) => (
                <Link className="list-row" to={`/notes/${note.id}`} key={note.id}>
                  <span className={`note-check${note.is_done ? ' is-done' : ''}`}>✓</span>
                  <span className="truncate">
                    <span className="list-row-title">{note.title}</span>
                    <span className="list-row-sub">
                      {' '}
                      by {note.author} · Semester {note.semester} · {note.branch}
                    </span>
                  </span>
                  <span className="spacer" />
                  <span className="badge">{note.kind_label}</span>
                  {subjectName(note.subject_id) ? (
                    <span className="badge badge-accent">{subjectName(note.subject_id)}</span>
                  ) : null}
                  {note.attachment_count > 0 ? (
                    <span className="badge">{note.attachment_count} file</span>
                  ) : null}
                  <span className="list-row-sub">{formatStamp(note.updated_at)}</span>
                </Link>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
