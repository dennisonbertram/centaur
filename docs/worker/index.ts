/// <reference types="@cloudflare/workers-types" />

interface Env {
  ASSETS: Fetcher
  COMMUNITY_SLACK_REQUESTS?: D1Database
  CONTACT_SUBMISSIONS?: D1Database
  DB?: D1Database
}

const createCommunitySlackRequestsTable = `
  CREATE TABLE IF NOT EXISTS community_slack_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    company TEXT NOT NULL,
    role TEXT NOT NULL,
    interest_reason TEXT NOT NULL,
    invite_status TEXT NOT NULL DEFAULT 'pending',
    source_path TEXT,
    user_agent TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
  )
`

function json(data: Record<string, unknown>, status = 200) {
  return Response.json(data, {
    status,
    headers: {
      'Cache-Control': 'no-store',
    },
  })
}

function isEmail(value: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)
}

function textField(body: Record<string, unknown> | null, key: string) {
  const value = body?.[key]
  return typeof value === 'string' ? value.trim() : ''
}

function tooLong(value: string, maxLength: number) {
  return value.length > maxLength
}

async function readSubmissionBody(request: Request) {
  const contentType = request.headers.get('content-type') ?? ''

  if (contentType.includes('application/json')) {
    return (await request.json().catch(() => null)) as Record<string, unknown> | null
  }

  if (
    contentType.includes('application/x-www-form-urlencoded') ||
    contentType.includes('multipart/form-data')
  ) {
    const form = await request.formData().catch(() => null)
    if (!form) return null

    return Object.fromEntries(
      Array.from(form.entries(), ([key, value]) => [
        key,
        typeof value === 'string' ? value : '',
      ]),
    )
  }

  return null
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url)
    const isContactSubmission =
      request.method === 'POST' &&
      (url.pathname === '/api/contact' || url.pathname === '/contact' || url.pathname === '/contact/')

    if (isContactSubmission) {
      const response = await handleContactSubmission(request, env)
      if (url.pathname !== '/api/contact' && response.ok) {
        return Response.redirect(new URL('/contact?submitted=1', url).toString(), 303)
      }
      return response
    }

    if (url.pathname.startsWith('/api/')) {
      return json({ error: 'Not found' }, 404)
    }

    return env.ASSETS.fetch(request)
  },
} satisfies ExportedHandler<Env>

async function handleContactSubmission(request: Request, env: Env) {
  const db = env.COMMUNITY_SLACK_REQUESTS ?? env.CONTACT_SUBMISSIONS ?? env.DB
  if (!db) return json({ error: 'Contact storage is not configured' }, 500)

  const body = await readSubmissionBody(request)

  const firstName = textField(body, 'firstName')
  const lastName = textField(body, 'lastName')
  const email = textField(body, 'email').toLowerCase()
  const company = textField(body, 'company')
  const role = textField(body, 'role')
  const interestReason = textField(body, 'interestReason')

  if (!firstName) return json({ error: 'First name is required' }, 400)
  if (!lastName) return json({ error: 'Surname is required' }, 400)
  if (!isEmail(email)) return json({ error: 'Valid email is required' }, 400)
  if (!company) return json({ error: 'Company is required' }, 400)
  if (!role) return json({ error: 'Role is required' }, 400)
  if (!interestReason) return json({ error: 'Please share why you are interested in Centaur' }, 400)
  if (tooLong(firstName, 120)) return json({ error: 'First name is too long' }, 400)
  if (tooLong(lastName, 120)) return json({ error: 'Surname is too long' }, 400)
  if (tooLong(email, 320)) return json({ error: 'Email is too long' }, 400)
  if (tooLong(company, 180)) return json({ error: 'Company is too long' }, 400)
  if (tooLong(role, 180)) return json({ error: 'Role is too long' }, 400)
  if (tooLong(interestReason, 4000)) {
    return json({ error: 'Please keep your answer under 4,000 characters' }, 400)
  }

  let sourcePath: string | null = null
  const referer = request.headers.get('referer')
  if (referer) {
    try {
      sourcePath = new URL(referer).pathname
    } catch {}
  }

  await db.prepare(createCommunitySlackRequestsTable).run()
  await db
    .prepare(
      `
        INSERT INTO community_slack_requests (
          email,
          first_name,
          last_name,
          company,
          role,
          interest_reason,
          source_path,
          user_agent,
          updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(email) DO UPDATE SET
          first_name = excluded.first_name,
          last_name = excluded.last_name,
          company = excluded.company,
          role = excluded.role,
          interest_reason = excluded.interest_reason,
          source_path = excluded.source_path,
          user_agent = excluded.user_agent,
          updated_at = datetime('now')
      `,
    )
    .bind(
      email,
      firstName,
      lastName,
      company,
      role,
      interestReason,
      sourcePath,
      request.headers.get('user-agent'),
    )
    .run()

  return json({ ok: true })
}
