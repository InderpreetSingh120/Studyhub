import { Link } from 'react-router-dom'

export function NotFoundPage() {
  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-head">
          <h1>Page not found</h1>
          <p className="muted">That address does not exist.</p>
        </div>
        <Link className="btn btn-primary btn-block" to="/">
          Back to the dashboard
        </Link>
      </div>
    </div>
  )
}
