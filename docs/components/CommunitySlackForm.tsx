'use client'

import { useEffect, useState, type FormEvent } from 'react'

type Status = {
  message: string
  type: '' | 'success' | 'error'
}

export default function CommunitySlackForm() {
  const [status, setStatus] = useState<Status>({ message: '', type: '' })
  const [isSubmitting, setIsSubmitting] = useState(false)

  useEffect(() => {
    if (new URLSearchParams(window.location.search).get('submitted') === '1') {
      setStatus({
        message: "Thanks. We'll follow up with the next Centaur Community Slack onboarding steps.",
        type: 'success',
      })
    }
  }, [])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    const form = event.currentTarget
    const data = new FormData(form)
    const payload = {
      firstName: String(data.get('firstName') || ''),
      lastName: String(data.get('lastName') || ''),
      email: String(data.get('email') || ''),
      company: String(data.get('company') || ''),
      role: String(data.get('role') || ''),
      interestReason: String(data.get('interestReason') || ''),
    }

    setStatus({ message: '', type: '' })
    setIsSubmitting(true)

    try {
      const endpoint = new URL('/api/contact', window.location.origin)
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })

      if (!response.ok) {
        const body = (await response.json().catch(() => ({}))) as { error?: string }
        throw new Error(body.error || 'Submission failed')
      }

      form.reset()
      setStatus({
        message: "Thanks. We'll follow up with the next Centaur Community Slack onboarding steps.",
        type: 'success',
      })
    } catch (error) {
      setStatus({
        message: error instanceof Error ? error.message : 'Submission failed',
        type: 'error',
      })
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <form
      className="contact-form"
      data-contact-form
      method="post"
      action="/api/contact"
      onSubmit={handleSubmit}
      aria-busy={isSubmitting}
    >
      <div className="contact-field-grid">
        <label>
          <span>First name</span>
          <input name="firstName" autoComplete="given-name" required />
        </label>

        <label>
          <span>Surname</span>
          <input name="lastName" autoComplete="family-name" required />
        </label>
      </div>

      <label>
        <span>Company</span>
        <input name="company" autoComplete="organization" required />
      </label>

      <label>
        <span>Role</span>
        <input name="role" autoComplete="organization-title" required />
      </label>

      <label>
        <span>Work email</span>
        <input name="email" type="email" autoComplete="email" required />
      </label>

      <label>
        <span>Why are you interested in Centaur?</span>
        <textarea name="interestReason" rows={5} required />
      </label>

      <button type="submit" disabled={isSubmitting}>
        {isSubmitting ? 'Requesting...' : 'Request Slack invite'}
      </button>
      <p
        className="contact-status"
        data-contact-status
        data-status={status.type}
        role="status"
        aria-live="polite"
      >
        {status.message}
      </p>
    </form>
  )
}
