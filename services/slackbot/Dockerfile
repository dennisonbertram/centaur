FROM node:22-slim AS base

RUN corepack enable pnpm

WORKDIR /app

# Install dependencies (cached independently of source changes)
COPY services/slackbot/package.json services/slackbot/pnpm-lock.yaml* ./
RUN pnpm install --frozen-lockfile 2>/dev/null || pnpm install

# Copy source and build
FROM base AS builder
COPY services/slackbot/ .
RUN pnpm build

# Production
FROM node:22-slim AS runner
RUN apt-get update && apt-get install -y --no-install-recommends curl jq && rm -rf /var/lib/apt/lists/*
WORKDIR /app

ENV NODE_ENV=production

# Next.js standalone output includes everything needed
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY scripts/bootstrap-secrets.sh /app/bootstrap-secrets.sh
COPY services/slackbot/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh /app/bootstrap-secrets.sh

EXPOSE 3001
ENV PORT=3001
ENV HOSTNAME="0.0.0.0"

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["node", "server.js"]
