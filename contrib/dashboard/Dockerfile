FROM node:24-slim AS base
RUN npm install -g pnpm@10

WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .
RUN pnpm build

ENV PORT=3000
EXPOSE 3000
CMD ["pnpm", "start"]
