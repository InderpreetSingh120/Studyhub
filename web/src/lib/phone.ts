/** Phone-number shaping shared by the sign-up form (the API applies the same rules). */

export function normalizePhone(raw: string): string {
  const digits = raw.replace(/\D/g, '')
  if (digits.length === 12 && digits.startsWith('91')) return digits.slice(2)
  if (digits.length === 13 && digits.startsWith('910')) return digits.slice(3)
  if (digits.length === 11 && digits.startsWith('0')) return digits.slice(1)
  return digits
}

export function isTenDigits(raw: string): boolean {
  return /^\d{10}$/.test(normalizePhone(raw))
}
