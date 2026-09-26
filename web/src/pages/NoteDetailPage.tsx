import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  attachments as attachmentsApi,
  downloadAttachment,
  notes as notesApi,
  openAttachment,
  subjects as subjectsApi,
} from '../api/endpoints'
import type { Attachment, Note, Subject } from '../api/types'
import { useAuth } from '../auth/useAuth'
import { Empty, ErrorNote, Loading, PageHeader } from '../components/ui'
import { formatDate, formatStamp } from '../lib/format'

const SUMMARY_HINT: Record<Attachment['summary_status'], string> = {
  pending: 'Writing a summary for this file…',
  ready: '',
  failed: 'The summary could not be generated for this file.',
  skipped: 'Summary skipped — AI summaries are turned off on this server.',
}

export function NoteDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()
  const noteId = Number(id)
  const invalid = !Number.isInteger(noteId)

  const [note, setNote] = useState<Note | null>(null)
  const [files, setFiles] = useState<Attachment[] | null>(null)
  const [subjects, setSubjects] = useState<Subject[]>([])
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)

  const mine = user !== null && (user.id === note?.author_id || user.role === 'admin')

  const load = useCallback(() => {
    if (invalid) return
    Promise.all([
      notesApi.get(noteId),
      attachmentsApi.list(noteId),
      subjectsApi.list().catch(() => [] as Subject[]),
    ])
      .then(([loaded, uploaded, subjectList]) => {
        setNote(loaded)
        setFiles(uploaded)
        setSubjects(subjectList)
        setError(null)
      })
      .catch(setError)
  }, [noteId, invalid])

  useEffect(() => {
    load()
  }, [load])

  function refreshAttachments() {
    if (invalid) return
    attachmentsApi
      .list(noteId)
      .then(setFiles)
      .catch(setError)
  }

  // The summary job runs on the server right after an upload; poll while it works.
  useEffect(() => {
    if (!files?.some((file) => file.summary_status === 'pending')) return
    const timer = window.setInterval(() => {
      attachmentsApi
        .list(noteId)
        .then(setFiles)
        .catch(() => undefined)
    }, 3000)
    return () => window.clearInterval(timer)
  }, [files, noteId])

  async function handleDelete() {
    if (!note) return
    if (!window.confirm(`Delete "${note.title}"? Its files go too.`)) return
    setBusy(true)
    setError(null)
    try {
      await notesApi.remove(note.id)
      navigate('/notes', { replace: true })
    } catch (cause) {
      setError(cause)
      setBusy(false)
    }
  }

  async function handleOpen(attachment: Attachment) {
    if (!note) return
    setError(null)
    try {
      const url = await openAttachment(note.id, attachment)
      window.open(url, '_blank', 'noopener')
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000)
    } catch (cause) {
      setError(cause)
    }
  }

  async function handleRemove(attachment: Attachment) {
    if (!note) return
    if (!window.confirm(`Delete "${attachment.filename}"?`)) return
    setError(null)
    try {
      await attachmentsApi.remove(note.id, attachment.id)
      refreshAttachments()
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

  if (!note || files === null) {
    return (
      <div className="page">
        <Loading label={error ? 'Loading the note…' : 'Opening the note…'} />
      </div>
    )
  }

  const summaries = files

  return (
    <div className="page">
      <PageHeader
        title={note.title}
        subtitle={`Shared by ${note.author} · updated ${formatDate(note.updated_at)}`}
        actions={
          <>
            <Link className="btn btn-ghost" to="/notes">
              Gallery
            </Link>
            {mine ? (
              <>
                <button
                  type="button"
                  className="btn btn-danger"
                  onClick={handleDelete}
                  disabled={busy}
                >
                  Delete
                </button>
                <Link className="btn btn-primary" to={`/notes/${note.id}/edit`}>
                  Edit
                </Link>
              </>
            ) : null}
          </>
        }
      />

      <ErrorNote error={error} />

      <div className="row" style={{ flexWrap: 'wrap' }}>
        <span className="badge badge-accent">{note.kind_label}</span>
        <span className="badge">Semester {note.semester}</span>
        <span className="badge">{note.branch}</span>
        {note.subject_id ? (
          <span className="badge">
            {subjects.find((item) => item.id === note.subject_id)?.name ??
              `Subject #${note.subject_id}`}
          </span>
        ) : null}
        <span className={`badge ${note.is_done ? 'badge-success' : ''}`}>
          {note.is_done ? 'Completed' : 'Open'}
        </span>
        <span className="muted">Uploaded {formatStamp(note.created_at)}</span>
      </div>

      <div className="cols">
        <section className="card">
          <div className="card-header">
            <h2>Notes</h2>
          </div>
          <div className="card-body">
            {note.body ? (
              <p className="note-body">{note.body}</p>
            ) : (
              <Empty title="No written notes">
                This entry only carries files — open them below.
              </Empty>
            )}
          </div>
        </section>

        <div className="stack">
          <section className="card">
            <div className="card-header">
              <h2>AI summary</h2>
              <span className="muted">from the uploaded PDF</span>
            </div>
            <div className="card-body stack stack-sm">
              {summaries.length === 0 ? (
                <p className="hint">
                  Upload a PDF and a short summary of it is generated
                  automatically.
                </p>
              ) : (
                summaries.map((file) => (
                  <div className="summary-box" key={file.id}>
                    <div className="list-row-title truncate">{file.filename}</div>
                    {file.summary_status === 'ready' && file.summary ? (
                      <p>{file.summary}</p>
                    ) : (
                      <p className="hint">{SUMMARY_HINT[file.summary_status]}</p>
                    )}
                  </div>
                ))
              )}
            </div>
          </section>

          <section className="card">
            <div className="card-header">
              <h2>Files</h2>
              <span className="muted">{files.length}</span>
            </div>
            <div className="card-body stack stack-sm">
              {files.length === 0 ? (
                <p className="hint">No files on this note yet.</p>
              ) : (
                files.map((attachment) => (
                  <div className="attachment-row" key={attachment.id}>
                    <span className="truncate" style={{ flex: 1 }}>
                      <span className="list-row-title">{attachment.filename}</span>
                      <span className="list-row-sub">
                        {' '}
                        {formatStamp(attachment.created_at)} ·{' '}
                        {attachment.content_type === 'application/pdf'
                          ? 'PDF'
                          : 'image'}
                      </span>
                    </span>
                    <button
                      type="button"
                      className="btn btn-sm"
                      onClick={() => void handleOpen(attachment)}
                    >
                      Open
                    </button>
                    <button
                      type="button"
                      className="btn btn-sm"
                      onClick={() => void downloadAttachment(note.id, attachment)}
                    >
                      Download
                    </button>
                    {mine ? (
                      <button
                        type="button"
                        className="btn btn-sm btn-danger"
                        onClick={() => void handleRemove(attachment)}
                      >
                        Remove
                      </button>
                    ) : null}
                  </div>
                ))
              )}
            </div>
          </section>
        </div>
      </div>
    </div>
  )
}
