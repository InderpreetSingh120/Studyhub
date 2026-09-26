import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import { ErrorNote } from '../components/ui'

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [identifier, setIdentifier] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await login(identifier, password)
      navigate('/', { replace: true })
    } catch (cause) {
      setError(cause)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-page">
      <form className="auth-card" onSubmit={handleSubmit}>
        <div className="auth-head">
          <span className="brand">
            <span className="brand-mark">S</span>
            StudyHub
          </span>
          <p className="muted">Shared notes, summaries and study chats</p>
        </div>

        <ErrorNote error={error} />

        <div className="field">
          <label htmlFor="login-identifier">Phone number or username</label>
          <input
            id="login-identifier"
            className="input"
            autoComplete="username"
            autoFocus
            required
            placeholder="9876543210"
            value={identifier}
            onChange={(event) => setIdentifier(event.target.value)}
          />
          <span className="hint">
            Your phone number is the safest option — usernames can be shared
          </span>
        </div>

        <div className="field">
          <label htmlFor="login-password">Password</label>
          <input
            id="login-password"
            className="input"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </div>

        <button
          type="submit"
          className="btn btn-primary btn-block"
          disabled={busy || !identifier || !password}
        >
          {busy ? 'Signing in…' : 'Sign in'}
        </button>

        <p className="auth-foot">
          No account yet? <Link to="/register">Create one</Link>
        </p>
      </form>
    </div>
  )
}
