/** Formatting helpers for the UTC timestamps the API hands back. */

export function parseApiDate(iso: string): Date {
  const trimmed = iso.replace(/(\.\d{3})\d+/, '$1')

  // A bare `YYYY-MM-DD` (trend buckets) is a calendar day, not an instant.
  const dateOnly = /^(\d{4})-(\d{2})-(\d{2})$/.exec(trimmed)
  if (dateOnly) {
    const [, year, month, day] = dateOnly
    return new Date(Number(year), Number(month) - 1, Number(day))
  }

  const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(trimmed)
  return new Date(hasZone ? trimmed : `${trimmed}Z`)
}

const dateOnly = new Intl.DateTimeFormat(undefined, {
  day: '2-digit',
  month: 'short',
  year: 'numeric',
})

const timeOnly = new Intl.DateTimeFormat(undefined, {
  hour: '2-digit',
  minute: '2-digit',
})

export function formatDate(iso: string): string {
  return dateOnly.format(parseApiDate(iso))
}

export function formatTime(iso: string): string {
  return timeOnly.format(parseApiDate(iso))
}

/** Time for messages written today, date plus time for older ones. */
export function formatStamp(iso: string): string {
  const date = parseApiDate(iso)
  const today = new Date()
  const sameDay =
    date.getFullYear() === today.getFullYear() &&
    date.getMonth() === today.getMonth() &&
    date.getDate() === today.getDate()
  return sameDay ? formatTime(iso) : `${formatDate(iso)} ${formatTime(iso)}`
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function initials(name: string): string {
  const parts = name.split(/[\s_.-]+/).filter(Boolean)
  if (parts.length === 0) return '?'
  if (parts.length === 1) return parts[0].slice(0, 2)
  return `${parts[0][0]}${parts[1][0]}`
}

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Something went wrong'
}
