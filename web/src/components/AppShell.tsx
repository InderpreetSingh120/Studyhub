import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import { initials } from '../lib/format'

export function AppShell() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    navigate('/login')
  }

  const navItems = [
    { to: '/', label: 'Dashboard', end: true },
    { to: '/notes', label: 'Gallery', end: false },
    { to: '/chat', label: 'Everyone chat', end: true },
    { to: '/groups', label: 'Groups', end: false },
    ...(user?.role === 'admin' ? [{ to: '/admin', label: 'Admin', end: true }] : []),
  ]

  return (
    <div className="shell">
      <aside className="sidebar">
        <NavLink to="/" className="brand">
          <span className="brand-mark">S</span>
          StudyHub
        </NavLink>

        <nav className="nav" aria-label="Main">
          <div className="nav-label">Study</div>
          {navItems.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.end}>
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="who">
            <span className="avatar">{initials(user?.username ?? '?')}</span>
            <div className="who-text">
              <div className="who-name">{user?.username}</div>
              <div className="who-sub truncate">
                {user?.phone}
                {user?.role === 'admin' ? ' · admin' : ''}
              </div>
            </div>
          </div>
          <button type="button" className="btn btn-ghost btn-sm" onClick={handleLogout}>
            Sign out
          </button>
        </div>
      </aside>

      <main className="main">
        <Outlet />
      </main>
    </div>
  )
}
