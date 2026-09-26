import { useMemo, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import { ErrorNote } from '../components/ui'
import { normalizePhone } from '../lib/phone'

const USERNAME = /^[A-Za-z]+(?: [A-Za-z]+)*$/

export function RegisterPage() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [phone, setPhone] = useState('')
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)

  const trimmedName = username.trim().replace(/\s+/g, ' ')
  const nameOk = USERNAME.test(trimmedName) && trimmedName.length >= 3
  const digits = normalizePhone(phone)
  const phoneOk = /^\d{10}$/.test(digits)
  const mismatch = confirmation.length > 0 && confirmation !== password

  const nameHint = useMemo(() => {
    if (!username || nameOk) return 'Letters and single spaces only, e.g. "Asha Verma"'
    return 'Use letters only — no numbers or symbols'
  }, [username, nameOk])

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!nameOk || !phoneOk || mismatch) return
    setBusy(true)
    setError(null)
    try {
      await register({ username: trimmedName, phone: digits, password })
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
          <p className="muted">Join the shared notes gallery</p>
        </div>

        <ErrorNote error={error} />

        <div className="field">
          <label htmlFor="register-username">Username</label>
          <input
            id="register-username"
            className="input"
            autoComplete="username"
            autoFocus
            required
            placeholder="Asha Verma"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
          />
          <span className={`hint${username && !nameOk ? ' error-text' : ''}`}>{nameHint}</span>
        </div>

        <div className="field">
          <label htmlFor="register-phone">Phone number</label>
          <input
            id="register-phone"
            className="input"
            type="tel"
            inputMode="tel"
            autoComplete="tel-national"
            required
            placeholder="98765 43210"
            value={phone}
            onChange={(event) => setPhone(event.target.value)}
          />
          <span className={`hint${phone && !phoneOk ? ' error-text' : ''}`}>
            {phoneOk
              ? `We will sign you in as ${digits}`
              : '10 digits; +91 and leading 0 are fine'}
          </span>
        </div>

        <div className="field">
          <label htmlFor="register-password">Password</label>
          <input
            id="register-password"
            className="input"
            type="password"
            autoComplete="new-password"
            required
            minLength={8}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
          <span className="hint">At least 8 characters</span>
        </div>

        <div className="field">
          <label htmlFor="register-confirm">Repeat password</label>
          <input
            id="register-confirm"
            className="input"
            type="password"
            autoComplete="new-password"
            required
            value={confirmation}
            onChange={(event) => setConfirmation(event.target.value)}
          />
          {mismatch ? (
            <span className="error-text">Passwords do not match</span>
          ) : null}
        </div>

        <div className="alert alert-warning">
          Your display name is visible to everyone. Accounts with unrecognized
          names may be renamed or removed by an administrator.
        </div>

        <button
          type="submit"
          className="btn btn-primary btn-block"
          disabled={busy || !nameOk || !phoneOk || mismatch || !password}
        >
          {busy ? 'Creating account…' : 'Create account'}
        </button>

        <p className="auth-foot">
          Already registered? <Link to="/login">Sign in</Link>
        </p>
      </form>
    </div>
  )
}
