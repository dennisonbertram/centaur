"use client";

import { useState } from "react";

type Credential = {
  name: string;
  key: string;
  description: string;
  masked: string;
  set: boolean;
};

const CREDENTIAL_GROUPS = [
  {
    title: "LLM Providers",
    credentials: [
      { name: "OPENAI_API_KEY", key: "openai", description: "For the Codex harness (default)", masked: "sk-proj-...Q0hc", set: true },
      { name: "ANTHROPIC_API_KEY", key: "anthropic", description: "For the Claude harness", masked: "", set: false },
    ],
  },
  {
    title: "Slack Integration",
    credentials: [
      { name: "SLACK_BOT_TOKEN", key: "slack_bot", description: "Bot User OAuth Token (xoxb-...)", masked: "", set: false },
      { name: "SLACK_SIGNING_SECRET", key: "slack_signing", description: "Verifies incoming Slack requests", masked: "", set: false },
    ],
  },
  {
    title: "Tool Credentials",
    credentials: [
      { name: "COMPOSIO_API_KEY", key: "composio", description: "Composio tool platform (1000+ integrations)", masked: "ak_AH...Q8", set: true },
      { name: "GITHUB_TOKEN", key: "github", description: "GitHub API access for agent sandboxes", masked: "", set: false },
    ],
  },
];

export default function CredentialsPage() {
  const [editing, setEditing] = useState<string | null>(null);

  return (
    <div className="mx-auto max-w-3xl px-4 py-10 sm:px-6 lg:px-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight">Credentials</h1>
        <p className="mt-1 text-sm text-gray-500">
          Credentials are injected into your deployment via iron-proxy.
          Agents never see raw keys.
        </p>
      </div>

      <div className="space-y-8">
        {CREDENTIAL_GROUPS.map((group) => (
          <div key={group.title}>
            <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">
              {group.title}
            </h2>
            <div className="rounded-lg border border-gray-200 bg-white divide-y divide-gray-100">
              {group.credentials.map((cred) => (
                <div
                  key={cred.key}
                  className="flex items-center justify-between px-4 py-3"
                >
                  <div>
                    <p className="text-sm font-medium font-mono">
                      {cred.name}
                    </p>
                    <p className="text-xs text-gray-500">{cred.description}</p>
                  </div>
                  <div className="flex items-center gap-3">
                    {cred.set ? (
                      <span className="flex items-center gap-1.5 text-xs text-green-700">
                        <span className="h-1.5 w-1.5 rounded-full bg-green-500" />
                        {cred.masked}
                      </span>
                    ) : (
                      <span className="text-xs text-gray-400">Not set</span>
                    )}
                    <button
                      onClick={() =>
                        setEditing(editing === cred.key ? null : cred.key)
                      }
                      className="rounded border border-gray-300 px-2.5 py-1 text-xs font-medium text-gray-700 hover:bg-gray-50"
                    >
                      {cred.set ? "Update" : "Add"}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
