"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";

type Cred = { masked: string; isSet: boolean };

export function SetupWizard({
  deploymentId,
  ip,
  webhookUrl,
  credentials: creds,
}: {
  deploymentId: string;
  ip: string | null;
  webhookUrl: string | null;
  credentials: Record<string, Cred>;
}) {
  const hasOpenAI = creds.OPENAI_API_KEY?.isSet;
  const hasValidWebhookUrl = webhookUrl?.startsWith("https://") ?? false;
  const currentStep = !hasOpenAI ? 1 : 2;

  return (
    <div className="space-y-6">
      {/* Progress */}
      <div className="flex items-center gap-3">
        <StepDot step={1} current={currentStep} />
        <div className="h-px flex-1 bg-border" />
        <StepDot step={2} current={currentStep} />
        <div className="h-px flex-1 bg-border" />
        <StepDot step={3} current={currentStep} label="Slack" dimmed={currentStep < 2} />
      </div>

      {/* Step 1 */}
      <Card className={currentStep === 1 ? "border-primary/50 shadow-sm" : currentStep > 1 ? "border-green-500/30 bg-green-500/5" : "opacity-50"}>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">
              {currentStep > 1 ? "✓ " : "1. "}Add your LLM API key
            </CardTitle>
            {creds.OPENAI_API_KEY?.isSet && (
              <Badge variant="outline" className="text-green-600 border-green-200">
                Configured
              </Badge>
            )}
          </div>
          <CardDescription>
            Your agent needs an API key to talk to an LLM. OpenAI is the default
            for the Codex harness.
          </CardDescription>
        </CardHeader>
        {currentStep <= 1 && (
          <CardContent>
            <CredentialForm
              deploymentId={deploymentId}
              credKey="OPENAI_API_KEY"
              label="OpenAI API Key"
              description="Get one at platform.openai.com/api-keys"
              placeholder="sk-proj-..."
              current={creds.OPENAI_API_KEY}
            />
          </CardContent>
        )}
      </Card>

      {/* Step 2 */}
      <Card className={currentStep === 2 ? "border-green-500/30 bg-green-500/5" : "opacity-50"}>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">
              {hasOpenAI ? "✓ " : "2. "}Your agent is ready
            </CardTitle>
            {hasOpenAI && (
              <Badge variant="outline" className="text-green-600 border-green-200">
                Healthy
              </Badge>
            )}
          </div>
          <CardDescription>
            Your Centaur instance is running and configured with an LLM key.
            Connect Slack below to start chatting, or use the API key to
            integrate programmatically.
          </CardDescription>
        </CardHeader>
      </Card>

      {/* Step 3: Slack */}
      <Card className={currentStep >= 2 ? "" : "opacity-50"}>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">3. Connect Slack</CardTitle>
            <Badge variant="outline">Optional</Badge>
          </div>
          <CardDescription>
            Create a Slack app and point it at your deployment to chat with your
            agent from Slack.
          </CardDescription>
        </CardHeader>
        {currentStep >= 2 && (
          <CardContent className="space-y-5">
            {hasValidWebhookUrl ? (
              <>
                <SlackInstructions webhookUrl={webhookUrl} />
                <Separator />
                <div className="space-y-4">
                  <CredentialForm
                    deploymentId={deploymentId}
                    credKey="SLACK_BOT_TOKEN"
                    label="Slack Bot Token"
                    description="Bot User OAuth Token (starts with xoxb-)"
                    placeholder="xoxb-..."
                    current={creds.SLACK_BOT_TOKEN}
                  />
                  <CredentialForm
                    deploymentId={deploymentId}
                    credKey="SLACK_SIGNING_SECRET"
                    label="Slack Signing Secret"
                    description="Found under Basic Information → App Credentials"
                    placeholder="abc123..."
                    current={creds.SLACK_SIGNING_SECRET}
                  />
                </div>
              </>
            ) : (
              <div className="rounded-lg border border-yellow-200 bg-yellow-50/50 dark:border-yellow-900 dark:bg-yellow-950/20 p-4 text-sm space-y-2">
                <p className="font-medium text-yellow-800 dark:text-yellow-200">
                  HTTPS required
                </p>
                <p className="text-xs text-yellow-700 dark:text-yellow-300">
                  Slack requires an HTTPS webhook URL. Your deployment is
                  reachable at <code className="bg-yellow-100 dark:bg-yellow-900 rounded px-1">{ip}</code> but
                  doesn&apos;t have a domain with TLS configured yet.
                </p>
                <p className="text-xs text-yellow-600 dark:text-yellow-400">
                  To enable Slack, point a domain at your cluster IP and
                  configure TLS (Let&apos;s Encrypt is already installed). Then
                  new deployments will automatically get HTTPS webhook URLs.
                </p>
              </div>
            )}
          </CardContent>
        )}
      </Card>

      {/* Optional credentials */}
      <details className="group">
        <summary className="cursor-pointer text-sm font-medium text-muted-foreground hover:text-foreground transition-colors list-none flex items-center gap-2">
          <svg
            className="h-4 w-4 transition-transform group-open:rotate-90"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <polyline points="9 18 15 12 9 6" />
          </svg>
          Additional credentials
        </summary>
        <div className="mt-4 space-y-4">
          <CredentialForm
            deploymentId={deploymentId}
            credKey="ANTHROPIC_API_KEY"
            label="Anthropic API Key"
            description="For the Claude harness (--claude flag). Optional."
            placeholder="sk-ant-..."
            current={creds.ANTHROPIC_API_KEY}
          />
          <CredentialForm
            deploymentId={deploymentId}
            credKey="COMPOSIO_API_KEY"
            label="Composio API Key"
            description="Enables 1000+ tool integrations. Get one at composio.dev"
            placeholder="ak_..."
            current={creds.COMPOSIO_API_KEY}
          />
        </div>
      </details>
    </div>
  );
}

function StepDot({
  step,
  current,
  label,
  dimmed,
}: {
  step: number;
  current: number;
  label?: string;
  dimmed?: boolean;
}) {
  const done = step < current;
  const active = step === current;
  return (
    <div className={`flex flex-col items-center gap-1 ${dimmed ? "opacity-40" : ""}`}>
      <div
        className={`flex h-8 w-8 items-center justify-center rounded-full text-xs font-medium transition-colors ${
          done
            ? "bg-green-500 text-white"
            : active
              ? "bg-primary text-primary-foreground"
              : "bg-muted text-muted-foreground"
        }`}
      >
        {done ? "✓" : step}
      </div>
      {label && (
        <span className="text-[10px] text-muted-foreground">{label}</span>
      )}
    </div>
  );
}

function SlackInstructions({ webhookUrl }: { webhookUrl: string | null }) {
  const url = webhookUrl || "https://YOUR_DOMAIN/api/webhooks/slack";

  return (
    <div className="rounded-lg border bg-blue-50/50 dark:bg-blue-950/20 p-4 text-sm space-y-3">
      <p className="font-medium text-blue-900 dark:text-blue-100">
        Slack app setup
      </p>
      <ol className="list-decimal list-outside ml-4 space-y-2.5 text-xs text-blue-800 dark:text-blue-200">
        <li>
          Go to{" "}
          <a
            href="https://api.slack.com/apps"
            target="_blank"
            rel="noopener noreferrer"
            className="underline font-medium"
          >
            api.slack.com/apps
          </a>{" "}
          → <strong>Create New App</strong> → From Scratch
        </li>
        <li>
          <strong>OAuth &amp; Permissions</strong> → Add these Bot Token Scopes:
          <div className="flex flex-wrap gap-1 mt-1">
            {["app_mentions:read", "channels:history", "groups:history", "im:history", "chat:write"].map(s => (
              <code key={s} className="bg-blue-100 dark:bg-blue-900 rounded px-1.5 py-0.5">{s}</code>
            ))}
          </div>
        </li>
        <li>
          <strong>Install App</strong> to your workspace
        </li>
        <li>
          <strong>Event Subscriptions</strong> → Enable Events → set Request URL:
          <div className="rounded border bg-background px-3 py-2 font-mono text-xs break-all mt-1">
            {url}
          </div>
          <p className="text-[10px] text-blue-600 dark:text-blue-400 mt-1">
            Slack will send a verification challenge to this URL. Your Centaur
            slackbot handles it automatically.
          </p>
        </li>
        <li>
          Subscribe to these <strong>bot events</strong>:
          <div className="flex flex-wrap gap-1 mt-1">
            {["app_mention", "message.channels", "message.groups", "message.im"].map(e => (
              <code key={e} className="bg-blue-100 dark:bg-blue-900 rounded px-1.5 py-0.5">{e}</code>
            ))}
          </div>
        </li>
        <li>
          Copy the <strong>Bot User OAuth Token</strong> (starts with{" "}
          <code className="bg-blue-100 dark:bg-blue-900 rounded px-1">xoxb-</code>) and the{" "}
          <strong>Signing Secret</strong> (under Basic Information → App
          Credentials) into the fields below
        </li>
      </ol>
    </div>
  );
}

function CredentialForm({
  deploymentId,
  credKey,
  label,
  description,
  placeholder,
  current,
}: {
  deploymentId: string;
  credKey: string;
  label: string;
  description: string;
  placeholder: string;
  current?: Cred;
}) {
  const [value, setValue] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSave() {
    if (!value.trim()) return;
    setSaving(true);
    setError(null);

    try {
      const res = await fetch(
        `/api/deployments/${deploymentId}/credentials`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name: credKey, value: value.trim() }),
        }
      );

      if (res.ok) {
        setSaved(true);
        setValue("");
        setTimeout(() => window.location.reload(), 1000);
      } else {
        const data = await res.json().catch(() => ({}));
        setError(data.error || "Failed to save");
      }
    } catch {
      setError("Network error");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium">{label}</p>
          <p className="text-xs text-muted-foreground">{description}</p>
        </div>
        {current?.isSet && (
          <Badge variant="outline" className="text-green-600 border-green-200 text-xs">
            {current.masked}
          </Badge>
        )}
      </div>

      {error && (
        <p className="text-xs text-destructive">{error}</p>
      )}

      {saved ? (
        <p className="text-xs text-green-600">Saved! Reloading...</p>
      ) : (
        <div className="flex gap-2">
          <Input
            type="password"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder={current?.isSet ? "Update value..." : placeholder}
            className="font-mono text-sm"
          />
          <Button
            onClick={handleSave}
            disabled={saving || !value.trim()}
            size="sm"
          >
            {saving ? "..." : current?.isSet ? "Update" : "Save"}
          </Button>
        </div>
      )}
    </div>
  );
}
