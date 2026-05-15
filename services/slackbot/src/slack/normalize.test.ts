import { describe, expect, it, mock } from 'bun:test'
import { normalizeSlackEnvelope } from './normalize'

const client = { token: 'slack-bot-token-test' } as any

describe('normalizeSlackEnvelope', () => {
  it('ignores message file_share carrier events', async () => {
    const fetchMock = mock(async () => new Response('unused'))
    const originalFetch = globalThis.fetch
    globalThis.fetch = fetchMock as any
    try {
      const normalized = await normalizeSlackEnvelope({
        envelope: {
          type: 'event_callback',
          team_id: 'T123',
          event_id: 'Ev-file-share',
          event: {
            type: 'message',
            subtype: 'file_share',
            user: 'U123',
            channel: 'C123',
            channel_type: 'channel',
            ts: '1778875070.942789',
            text: '<@UBOT> what are these?',
            files: [
              {
                id: 'F123',
                name: 'image.png',
                mimetype: 'image/png',
                url_private_download: 'https://files.slack.test/F123'
              }
            ]
          }
        },
        botUserId: 'UBOT',
        client
      })

      expect(normalized).toBeNull()
      expect(fetchMock).not.toHaveBeenCalled()
    } finally {
      globalThis.fetch = originalFetch
    }
  })

  it('keeps app_mention events with files actionable', async () => {
    const fetchMock = mock(
      async () =>
        new Response(new Uint8Array([1, 2, 3]), {
          headers: { 'content-type': 'image/png' }
        })
    )
    const originalFetch = globalThis.fetch
    globalThis.fetch = fetchMock as any
    try {
      const normalized = await normalizeSlackEnvelope({
        envelope: {
          type: 'event_callback',
          team_id: 'T123',
          event_id: 'Ev-app-mention',
          event: {
            type: 'app_mention',
            user: 'U123',
            channel: 'C123',
            channel_type: 'channel',
            ts: '1778875070.942789',
            text: '<@UBOT> what are these?',
            files: [
              {
                id: 'F123',
                name: 'image.png',
                mimetype: 'image/png',
                url_private_download: 'https://files.slack.test/F123'
              }
            ]
          }
        },
        botUserId: 'UBOT',
        client
      })

      expect(normalized?.is_mention).toBe(true)
      expect(normalized?.parts).toHaveLength(2)
      expect(normalized?.parts[1]).toMatchObject({
        type: 'image',
        name: 'image.png',
        mime_type: 'image/png',
        slack_file_id: 'F123'
      })
      expect(fetchMock).toHaveBeenCalledTimes(1)
    } finally {
      globalThis.fetch = originalFetch
    }
  })
})
