import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { dashboard } from '../api/endpoints'
import type { Dashboard, LabelCount } from '../api/types'
import { Empty, ErrorNote, Loading, PageHeader } from '../components/ui'
import { formatDate, formatStamp } from '../lib/format'

function Bars({ rows, link }: { rows: LabelCount[]; link?: (key: string) => string }) {
  const widest = Math.max(1, ...rows.map((row) => row.count))
  if (rows.length === 0) {
    return <p className="hint">Nothing filed under this yet.</p>
  }
  return (
    <div className="bars">
      {rows.map((row) => {
        const label = link ? (
          <Link to={link(row.key)} className="truncate">
            {row.label}
          </Link>
        ) : (
          <span className="truncate">{row.label}</span>
        )
        return (
          <div className="bar-row" key={row.key}>
            {label}
            <span className="bar-track">
              <span
                className="bar-fill"
                style={{ width: `${(row.count / widest) * 100}%` }}
              />
            </span>
            <span className="bar-count">{row.count}</span>
          </div>
        )
      })}
    </div>
  )
}

export function DashboardPage() {
  const [data, setData] = useState<Dashboard | null>(null)
  const [error, setError] = useState<unknown>(null)

  const load = useCallback(() => {
    dashboard
      .get()
      .then((summary) => {
        setData(summary)
        setError(null)
      })
      .catch(setError)
  }, [])

  useEffect(() => {
    load()
  }, [load])

  if (error) {
    return (
      <div className="page">
        <PageHeader title="Dashboard" />
        <ErrorNote error={error} />
        <div>
          <button
            type="button"
            className="btn"
            onClick={() => {
              setError(null)
              load()
            }}
          >
            Try again
          </button>
        </div>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="page">
        <Loading label="Loading the dashboard…" />
      </div>
    )
  }

  const { notes, recent_notes, groups, trend } = data
  const percent = notes.total ? Math.round((notes.done / notes.total) * 100) : 0
  const widestSubject = Math.max(1, ...notes.by_subject.map((item) => item.count))
  const busiestDay = Math.max(1, ...trend.map((point) => point.count))
  const createdRecently = trend.reduce((sum, point) => sum + point.count, 0)
  const activeBranches = notes.by_branch.filter((row) => row.count > 0)

  return (
    <div className="page">
      <PageHeader
        title="Dashboard"
        subtitle="The shared library at a glance, plus the groups you belong to"
        actions={
          <Link className="btn btn-primary" to="/notes/new">
            Upload a note
          </Link>
        }
      />

      <div className="stat-grid">
        <div className="stat">
          <span className="stat-label">Notes shared</span>
          <span className="stat-value">{notes.total}</span>
          <span className="stat-sub">visible to everyone</span>
        </div>
        <div className="stat">
          <span className="stat-label">Completed</span>
          <span className="stat-value">{notes.done}</span>
          <span className="stat-sub">{percent}% of the library</span>
        </div>
        <div className="stat">
          <span className="stat-label">Subjects</span>
          <span className="stat-value">{notes.by_subject.length}</span>
          <span className="stat-sub">{notes.without_subject} not filed yet</span>
        </div>
        <div className="stat">
          <span className="stat-label">Your groups</span>
          <span className="stat-value">{groups.length}</span>
          <span className="stat-sub">
            {groups.filter((group) => group.last_message).length} with recent chat
          </span>
        </div>
      </div>

      <div className="cols">
        <section className="card">
          <div className="card-header">
            <h2>Notes by subject</h2>
            <Link to="/notes">Open the gallery</Link>
          </div>
          <div className="card-body">
            {notes.by_subject.length === 0 ? (
              <Empty title="No subjects yet">
                Add a subject while uploading a note, then counts show up here.
              </Empty>
            ) : (
              <div className="bars">
                {notes.by_subject.map((subject) => (
                  <div className="bar-row" key={subject.subject_id}>
                    <Link
                      to={`/notes?subject=${subject.subject_id}`}
                      className="truncate"
                    >
                      {subject.name}
                    </Link>
                    <span className="bar-track">
                      <span
                        className="bar-fill"
                        style={{
                          width: `${(subject.count / widestSubject) * 100}%`,
                          background: subject.color ?? undefined,
                        }}
                      />
                    </span>
                    <span className="bar-count">{subject.count}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>

        <section className="card">
          <div className="card-header">
            <h2>Notes added, last 30 days</h2>
            <span className="muted">{createdRecently} new</span>
          </div>
          <div className="card-body">
            <div
              className="trend"
              role="img"
              aria-label={`Notes added per day over the last 30 days, ${createdRecently} in total`}
            >
              {trend.map((point) => (
                <div
                  className="trend-col"
                  key={point.date}
                  title={`${formatDate(point.date)}: ${point.count} note${
                    point.count === 1 ? '' : 's'
                  }`}
                >
                  <div
                    className="trend-col-fill"
                    style={{ height: `${(point.count / busiestDay) * 100}%` }}
                  />
                </div>
              ))}
            </div>
            <div className="trend-axis">
              <span>{formatDate(trend[0]?.date ?? '')}</span>
              <span>{formatDate(trend[trend.length - 1]?.date ?? '')}</span>
            </div>
          </div>
        </section>
      </div>

      <div className="cols">
        <section className="card">
          <div className="card-header">
            <h2>By type</h2>
            <Link to="/notes">Filter</Link>
          </div>
          <div className="card-body stack">
            <Bars rows={notes.by_kind} link={(key) => `/notes?kind=${key}`} />
            <h3 className="muted">Branches</h3>
            <Bars rows={activeBranches} link={(key) => `/notes?branch=${key}`} />
          </div>
        </section>

        <section className="card">
          <div className="card-header">
            <h2>By semester</h2>
            <Link to="/notes">Filter</Link>
          </div>
          <div className="card-body">
            <Bars rows={notes.by_semester} link={(key) => `/notes?semester=${key}`} />
          </div>
        </section>
      </div>

      <div className="cols">
        <section className="card">
          <div className="card-header">
            <h2>Recently edited</h2>
            <Link to="/notes">All notes</Link>
          </div>
          {recent_notes.length === 0 ? (
            <Empty
              title="Nothing here yet"
              action={
                <Link className="btn btn-primary btn-sm" to="/notes/new">
                  Share the first note
                </Link>
              }
            />
          ) : (
            <div className="list">
              {recent_notes.map((note) => (
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
                  <span className="list-row-sub">{formatStamp(note.updated_at)}</span>
                </Link>
              ))}
            </div>
          )}
        </section>

        <section className="card">
          <div className="card-header">
            <h2>Your groups</h2>
            <Link to="/groups">Manage</Link>
          </div>
          {groups.length === 0 ? (
            <Empty
              title="No groups yet"
              action={
                <Link className="btn btn-primary btn-sm" to="/groups">
                  Start a group
                </Link>
              }
            />
          ) : (
            <div className="list">
              {groups.map((group) => (
                <Link className="list-row" to={`/groups/${group.id}`} key={group.id}>
                  <span>
                    <span className="list-row-title">{group.name}</span>
                    <span className="list-row-sub">
                      {' '}
                      · {group.member_count} member
                      {group.member_count === 1 ? '' : 's'}
                    </span>
                  </span>
                  <span className="spacer" />
                  <span className="list-row-sub truncate" style={{ maxWidth: '45%' }}>
                    {group.last_message
                      ? `${group.last_message.sender}: ${group.last_message.body}`
                      : 'No messages yet'}
                  </span>
                </Link>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
