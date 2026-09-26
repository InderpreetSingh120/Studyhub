import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  attachments as attachmentsApi,
  downloadAttachment,
  notes as notesApi,
  subjects as subjectsApi,
} from '../api/endpoints'
import { BRANCHES, KIND_LABELS, NOTE_KINDS, type Attachment, type Note, type NoteKind, type Subject } from '../api/types'
import { ErrorNote, Loading, PageHeader } from '../components/ui'
import { formatBytes, formatDate } from '../lib/format'

const SEMESTERS = [1, 2, 3, 4, 5, 6, 7, 8]

interface Draft {
  title: string
  body: string
  subject_id: number | null
  semester: number
  branch: string
  kind: NoteKind
  is_done: boolean
}

const EMPTY_DRAFT: Draft = {
  title: '',
  body: '',
  subject_id: null,
  semester: 1,
  branch: 'CSE',
  kind: 'notes',
  is_done: false,
}

export function NoteEditorPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  // `/notes/new` is a static route, so it carries no `:id` param.
  const isNew = id === undefined || id === 'new'
  const noteId = isNew ? null : Number(id)

  const [subjects, setSubjects] = useState<Subject[] | null>(null)
  const [draft, setDraft] = useState<Draft>(EMPTY_DRAFT)
  const [note, setNote] = useState<Note | null>(null)
  const [files, setFiles] = useState<Attachment[] | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)
  const [saved, setSaved] = useState(false)
  const invalid = !isNew && !Number.isInteger(noteId)

  useEffect(() => {
    if (invalid) return
    let cancelled = false
    async function load() {
      setError(null)
      try {
        const list = await subjectsApi.list()
        if (cancelled) return
        setSubjects(list)
        if (noteId !== null) {
          const loaded = await notesApi.get(noteId)
          const uploaded = await attachmentsApi.list(noteId)
          if (cancelled) return
          setNote(loaded)
          setFiles(uploaded)
          setDraft({
            title: loaded.title,
            body: loaded.body,
            subject_id: loaded.subject_id,
            semester: loaded.semester,
            branch: loaded.branch,
            kind: loaded.kind,
            is_done: loaded.is_done,
          })
        } else {
          setFiles([])
        }
      } catch (cause) {
        if (!cancelled) setError(cause)
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [noteId, invalid])

  async function handleSave(event: FormEvent) {
    event.preventDefault()
    if (!draft.title.trim()) {
      setError(new Error('A note needs a title'))
      return
    }
    setBusy(true)
    setError(null)
    try {
      if (noteId === null) {
        const created = await notesApi.create(draft)
        navigate(`/notes/${created.id}`, { replace: true })
      } else {
        const updated = await notesApi.update(noteId, draft)
        setNote(updated)
        setSaved(true)
      }
    } catch (cause) {
      setError(cause)
    } finally {
      setBusy(false)
    }
  }

  async function handleDelete() {
    if (noteId === null) return
    if (!window.confirm(`Delete "${draft.title || 'this note'}"? Its files go too.`))
      return
    setBusy(true)
    setError(null)
    try {
      await notesApi.remove(noteId)
      navigate('/notes', { replace: true })
    } catch (cause) {
      setError(cause)
      setBusy(false)
    }
  }

  async function handleUpload(fileList: FileList | null) {
    const file = fileList?.[0]
    if (!file || noteId === null) return
    setBusy(true)
    setError(null)
    try {
      await attachmentsApi.upload(noteId, file)
      setFiles(await attachmentsApi.list(noteId))
    } catch (cause) {
      setError(cause)
    } finally {
      setBusy(false)
      const input = document.getElementById('attachment-input') as HTMLInputElement | null
      if (input) input.value = ''
    }
  }

  async function handleDeleteAttachment(attachment: Attachment) {
    if (noteId === null) return
    if (!window.confirm(`Delete "${attachment.filename}"?`)) return
    setError(null)
    try {
      await attachmentsApi.remove(noteId, attachment.id)
      setFiles(await attachmentsApi.list(noteId))
    } catch (cause) {
      setError(cause)
    }
  }

  if (invalid) {
    return (
      <div className="page">
        <PageHeader title="Note" />
        <ErrorNote error={new Error('That note address is not valid')} />
        <div>
          <Link className="btn" to="/notes">
            Back to the gallery
          </Link>
        </div>
      </div>
    )
  }

  if (!subjects || files === null) {
    return (
      <div className="page">
        <Loading label={isNew ? 'Preparing a new entry…' : 'Loading the note…'} />
      </div>
    )
  }

  return (
    <div className="page">
      <PageHeader
        title={isNew ? 'Upload a note' : draft.title || 'Untitled note'}
        subtitle={
          note
            ? `Created ${formatDate(note.created_at)} · last edited ${formatDate(note.updated_at)}`
            : 'File it under a subject, semester and type'
        }
        actions={
          <>
            <Link
              className="btn btn-ghost"
              to={isNew ? '/notes' : `/notes/${noteId}`}
            >
              Back
            </Link>
            {!isNew ? (
              <button
                type="button"
                className="btn btn-danger"
                onClick={handleDelete}
                disabled={busy}
              >
                Delete
              </button>
            ) : null}
            <button
              type="submit"
              form="note-form"
              className="btn btn-primary"
              disabled={busy || draft.title.trim().length === 0}
            >
              {busy ? 'Saving…' : 'Save'}
            </button>
          </>
        }
      />

      <ErrorNote error={error} />
      {saved ? <div className="alert alert-info">Note saved.</div> : null}

      <form id="note-form" className="editor-grid" onSubmit={handleSave}>
        <section className="card">
          <div className="card-body stack">
            <div className="field">
              <label htmlFor="note-title">Title</label>
              <input
                id="note-title"
                className="input"
                maxLength={200}
                placeholder="Wave equation"
                value={draft.title}
                onChange={(event) => {
                  setSaved(false)
                  setDraft({ ...draft, title: event.target.value })
                }}
              />
            </div>
            <div className="field">
              <label htmlFor="note-body">Notes</label>
              <textarea
                id="note-body"
                className="textarea"
                rows={18}
                placeholder="Write as much as you like…"
                value={draft.body}
                onChange={(event) => {
                  setSaved(false)
                  setDraft({ ...draft, body: event.target.value })
                }}
              />
            </div>
          </div>
        </section>

        <div className="stack">
          <section className="card">
            <div className="card-header">
              <h2>Where it belongs</h2>
            </div>
            <div className="card-body stack stack-sm">
              <div className="field">
                <label htmlFor="note-subject">Subject</label>
                <select
                  id="note-subject"
                  className="select"
                  value={draft.subject_id ?? ''}
                  onChange={(event) =>
                    setDraft({
                      ...draft,
                      subject_id: event.target.value ? Number(event.target.value) : null,
                    })
                  }
                >
                  <option value="">No subject</option>
                  {subjects.map((subject) => (
                    <option key={subject.id} value={subject.id}>
                      {subject.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="field">
                <label htmlFor="note-semester">Semester</label>
                <select
                  id="note-semester"
                  className="select"
                  value={draft.semester}
                  onChange={(event) =>
                    setDraft({ ...draft, semester: Number(event.target.value) })
                  }
                >
                  {SEMESTERS.map((value) => (
                    <option key={value} value={value}>
                      Semester {value}
                    </option>
                  ))}
                </select>
              </div>

              <div className="field">
                <label htmlFor="note-branch">Branch</label>
                <input
                  id="note-branch"
                  className="input"
                  list="branch-options"
                  maxLength={40}
                  placeholder="CSE"
                  value={draft.branch}
                  onChange={(event) =>
                    setDraft({ ...draft, branch: event.target.value })
                  }
                />
                <datalist id="branch-options">
                  {BRANCHES.map((value) => (
                    <option key={value} value={value} />
                  ))}
                </datalist>
              </div>

              <div className="field">
                <label htmlFor="note-kind">Type</label>
                <select
                  id="note-kind"
                  className="select"
                  value={draft.kind}
                  onChange={(event) =>
                    setDraft({ ...draft, kind: event.target.value as NoteKind })
                  }
                >
                  {NOTE_KINDS.map((value) => (
                    <option key={value} value={value}>
                      {KIND_LABELS[value]}
                    </option>
                  ))}
                </select>
              </div>

              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={draft.is_done}
                  onChange={(event) =>
                    setDraft({ ...draft, is_done: event.target.checked })
                  }
                />
                Mark as completed
              </label>
            </div>
          </section>

          <section className="card">
            <div className="card-header">
              <h2>Files</h2>
              <span className="muted">{files.length}</span>
            </div>
            <div className="card-body stack stack-sm">
              {isNew ? (
                <p className="hint">
                  Save the entry first, then attach the PDF — a summary is
                  generated automatically.
                </p>
              ) : (
                <>
                  <label className="dropzone" htmlFor="attachment-input">
                    <span>PDF or image, up to 20 MB</span>
                    <input
                      id="attachment-input"
                      type="file"
                      accept="application/pdf,image/*"
                      style={{ maxWidth: '100%' }}
                      onChange={(event) => void handleUpload(event.target.files)}
                      disabled={busy}
                    />
                  </label>

                  {files.length === 0 ? (
                    <p className="hint">No files yet.</p>
                  ) : (
                    <div>
                      {files.map((attachment) => (
                        <div className="attachment-row" key={attachment.id}>
                          <span className="truncate" style={{ flex: 1 }}>
                            <span className="list-row-title">{attachment.filename}</span>
                            <span className="list-row-sub">
                              {' '}
                              {formatBytes(attachment.size_bytes)}
                            </span>
                          </span>
                          <button
                            type="button"
                            className="btn btn-sm"
                            onClick={() => {
                              if (noteId !== null) {
                                void downloadAttachment(noteId, attachment)
                              }
                            }}
                          >
                            Download
                          </button>
                          <button
                            type="button"
                            className="btn btn-sm btn-danger"
                            onClick={() => void handleDeleteAttachment(attachment)}
                          >
                            Remove
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>
          </section>
        </div>
      </form>
    </div>
  )
}
