import { writeFileSync } from 'node:fs'

const databaseId = process.env.CLOUDFLARE_D1_DATABASE_ID?.trim()
const databaseName =
  process.env.CLOUDFLARE_D1_DATABASE_NAME?.trim() || 'centaur-docs-community-slack-requests'

if (!databaseId) {
  console.error('CLOUDFLARE_D1_DATABASE_ID is required to write the deploy Wrangler config.')
  process.exit(1)
}

const config = {
  $schema: './node_modules/wrangler/config-schema.json',
  name: 'centaur-docs',
  main: './worker/index.ts',
  compatibility_date: '2026-05-05',
  preview_urls: true,
  routes: [
    {
      pattern: 'centaur.run',
      custom_domain: true,
    },
  ],
  assets: {
    directory: './dist/public',
    binding: 'ASSETS',
    run_worker_first: true,
    html_handling: 'drop-trailing-slash',
    not_found_handling: '404-page',
  },
  d1_databases: [
    {
      binding: 'COMMUNITY_SLACK_REQUESTS',
      database_name: databaseName,
      database_id: databaseId,
      migrations_dir: 'migrations',
    },
  ],
  build: {
    command: 'npm run build',
  },
}

writeFileSync('wrangler.generated.jsonc', `${JSON.stringify(config, null, 2)}\n`)
