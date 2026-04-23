# Tutorial: Building a Web App

End-to-end walkthrough: build a web app locally, test it against the Centaur API, deploy it to Centaur, and share it.

We'll build a simple Next.js app that lets you chat with a Centaur agent through a web UI.

---

## Step 1: Scaffold locally

### Option A: Use the template (fastest)

```bash
# Clone the template
gh repo clone paradigmxyz/centaur-template-nextjs my-hackathon-app
cd my-hackathon-app
npm install
```

### Option B: Start from scratch

```bash
npx create-next-app@latest my-hackathon-app
cd my-hackathon-app
```

---

## Step 2: Connect to the Centaur API

Your app talks to the hosted Centaur API at `https://svc-ai.dayno.xyz`. Add your API key to a local `.env.local`:

```bash
echo 'CENTAUR_API_KEY=aiv2_your_key_here' >> .env.local
echo 'CENTAUR_API_URL=https://svc-ai.dayno.xyz' >> .env.local
```

### Example: API route that spawns an agent and streams the response

```typescript
// app/api/chat/route.ts
import { NextRequest } from 'next/server';

const API = process.env.CENTAUR_API_URL!;
const KEY = process.env.CENTAUR_API_KEY!;

async function centaurFetch(path: string, body?: object) {
  const res = await fetch(`${API}${path}`, {
    method: body ? 'POST' : 'GET',
    headers: {
      'Content-Type': 'application/json',
      'X-Api-Key': KEY,
    },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  return res.json();
}

export async function POST(req: NextRequest) {
  const { message, threadKey } = await req.json();
  const thread = threadKey || `web-${Date.now()}`;

  // 1. Spawn
  const spawn = await centaurFetch('/agent/spawn', {
    thread_key: thread,
    harness: 'amp',
  });

  // 2. Message
  await centaurFetch('/agent/message', {
    thread_key: thread,
    assignment_generation: spawn.assignment_generation,
    role: 'user',
    parts: [{ type: 'text', text: message }],
  });

  // 3. Execute
  const exec = await centaurFetch('/agent/execute', {
    thread_key: thread,
    assignment_generation: spawn.assignment_generation,
    harness: 'amp',
    delivery: { platform: 'dev' },
  });

  // 4. Stream events back to the client
  const eventsUrl = `${API}/agent/threads/${thread}/events?execution_id=${exec.execution_id}&after_event_id=0`;
  const eventsRes = await fetch(eventsUrl, {
    headers: { 'X-Api-Key': KEY },
  });

  return new Response(eventsRes.body, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
    },
  });
}
```

### Example: Call a tool directly

```typescript
// Anywhere in your app
const res = await fetch(`${API}/tools/websearch/search`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-Api-Key': KEY,
  },
  body: JSON.stringify({ query: 'latest crypto news', num_results: 5 }),
});
const data = await res.json();
```

---

## Step 3: Run and test locally

```bash
npm run dev
```

Open `http://localhost:3000` and test your app. It will call the hosted Centaur API — no local Centaur stack needed.

### Things to verify

- [ ] API key auth works (no 401 errors)
- [ ] Agent spawn/message/execute flow completes
- [ ] Events stream back correctly
- [ ] UI renders the agent's response
- [ ] Tool calls work (if using them directly)

### Debugging tips

```bash
# Test the API directly to rule out app issues
curl -s https://svc-ai.dayno.xyz/health -H "X-Api-Key: $CENTAUR_API_KEY"

# Check if a specific tool works
curl -s https://svc-ai.dayno.xyz/tools/websearch \
  -H "X-Api-Key: $CENTAUR_API_KEY" | python3 -m json.tool
```

---

## Step 4: Push to GitHub

Your app needs to be in a GitHub repo for Centaur to deploy it:

```bash
# If you used the template, update the remote
git remote set-url origin https://github.com/YOUR_USERNAME/my-hackathon-app

# If you started from scratch
git init
git add .
git commit -m "hackathon: initial app"
gh repo create my-hackathon-app --public --push
```

---

## Step 5: Deploy to Centaur

```bash
curl -s -X POST https://svc-ai.dayno.xyz/apps \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: $CENTAUR_API_KEY" \
  -d '{
    "name": "my-hackathon-app",
    "repo_url": "https://github.com/YOUR_USERNAME/my-hackathon-app",
    "port": 3000,
    "env": {
      "CENTAUR_API_URL": "http://api:8000",
      "CENTAUR_API_KEY": ""
    }
  }' | python3 -m json.tool
```

> **Note**: When running on Centaur's infrastructure, your app is on the internal Docker network. Set `CENTAUR_API_URL` to `http://api:8000` (internal) and `CENTAUR_API_KEY` can be empty (localhost bypass — no key needed for internal calls).

Your app will be live at: **`https://my-hackathon-app.svc-ai.dayno.xyz`**

---

## Step 6: Check status and debug

```bash
# Check app status
curl -s https://svc-ai.dayno.xyz/apps/my-hackathon-app \
  -H "X-Api-Key: $CENTAUR_API_KEY" | python3 -m json.tool

# View build logs (if something failed)
curl -s https://svc-ai.dayno.xyz/apps/my-hackathon-app/logs \
  -H "X-Api-Key: $CENTAUR_API_KEY" | python3 -m json.tool
```

### Common issues

| Problem | Fix |
|---------|-----|
| Build fails | Check build logs. Missing dependency? Wrong Node version? |
| App starts but 502 | Wrong `port` — make sure it matches what your app listens on |
| Can't reach Centaur API | Use `http://api:8000` (internal), not `https://svc-ai.dayno.xyz` |
| Auth errors from app | On internal network, no API key needed. Set `CENTAUR_API_KEY=""` |

---

## Step 7: Iterate

Push changes to your repo, then restart:

```bash
# After git push
curl -s -X POST https://svc-ai.dayno.xyz/apps/my-hackathon-app/restart \
  -H "X-Api-Key: $CENTAUR_API_KEY"
```

This rebuilds from the latest git and restarts.

---

## Non-Node.js apps

You can deploy Python, Go, or anything else. Use custom build and start commands:

### Python (Flask/FastAPI)

```bash
curl -s -X POST https://svc-ai.dayno.xyz/apps \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: $CENTAUR_API_KEY" \
  -d '{
    "name": "my-python-app",
    "repo_url": "https://github.com/YOUR_USERNAME/my-app",
    "port": 8080,
    "build_cmd": "pip install -r requirements.txt",
    "start_cmd": "python main.py"
  }'
```

### Static site

```bash
curl -s -X POST https://svc-ai.dayno.xyz/apps \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: $CENTAUR_API_KEY" \
  -d '{
    "name": "my-site",
    "repo_url": "https://github.com/YOUR_USERNAME/my-site",
    "port": 8080,
    "build_cmd": "npm install && npm run build",
    "start_cmd": "npx serve dist -l 8080"
  }'
```

---

## Password protection

Add basic auth to restrict access:

```bash
curl -s -X POST https://svc-ai.dayno.xyz/apps \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: $CENTAUR_API_KEY" \
  -d '{
    "name": "my-private-app",
    "repo_url": "https://github.com/YOUR_USERNAME/my-app",
    "port": 3000,
    "basic_auth_user": "hackathon",
    "basic_auth_pass": "secret123"
  }'
```

---

## Managing apps

```bash
# List all apps
curl -s https://svc-ai.dayno.xyz/apps -H "X-Api-Key: $CENTAUR_API_KEY"

# Restart (rebuild from latest git)
curl -s -X POST https://svc-ai.dayno.xyz/apps/<name>/restart -H "X-Api-Key: $CENTAUR_API_KEY"

# Delete
curl -s -X DELETE https://svc-ai.dayno.xyz/apps/<name> -H "X-Api-Key: $CENTAUR_API_KEY"
```

---

## Checklist

- [ ] App runs locally with `npm run dev` (or equivalent)
- [ ] Connects to Centaur API successfully (health check passes)
- [ ] Core functionality works locally (agent chat, tool calls, etc.)
- [ ] Code is pushed to a GitHub repo
- [ ] Deployed via `POST /apps` with correct `port`
- [ ] App loads at `https://<name>.svc-ai.dayno.xyz`
- [ ] On internal network, uses `http://api:8000` (no API key needed)
