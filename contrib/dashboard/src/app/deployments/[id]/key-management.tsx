"use client";

import { useMemo, useState } from "react";
import { Copy, KeyRound, Plus, Trash2, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";

export type ApiKeyListItem = {
  id: string;
  keyPrefix: string;
  name: string;
  createdAt: string;
  lastUsedAt: string | null;
};

type RevealedKey = {
  id: string;
  key: string;
  name: string;
  keyPrefix: string;
};

const dateFormatter = new Intl.DateTimeFormat(undefined, {
  month: "short",
  day: "numeric",
  year: "numeric",
});

export function KeyManagement({
  deploymentId,
  initialKeys,
  initialRevealedKeys,
}: {
  deploymentId: string;
  initialKeys: ApiKeyListItem[];
  initialRevealedKeys: RevealedKey[];
}) {
  const [keys, setKeys] = useState(initialKeys);
  const [revealedKeys, setRevealedKeys] = useState<RevealedKey[]>(initialRevealedKeys);
  const [isCreating, setIsCreating] = useState(false);
  const [name, setName] = useState("");
  const [busyKeyId, setBusyKeyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function createKey() {
    setError(null);
    setIsCreating(true);
    try {
      const res = await fetch(`/api/deployments/${deploymentId}/keys`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });
      const data = await res.json().catch(() => ({})) as {
        key?: string;
        keyRecord?: ApiKeyListItem;
        error?: string;
      };
      if (!res.ok || !data.key || !data.keyRecord) {
        setError(data.error || "Failed to create key");
        return;
      }
      setKeys((current) => [...current, data.keyRecord!]);
      setRevealedKeys((current) => [{
        id: data.keyRecord!.id,
        key: data.key!,
        name: data.keyRecord!.name,
        keyPrefix: data.keyRecord!.keyPrefix,
      }, ...current]);
      setName("");
    } catch {
      setError("Network error");
    } finally {
      setIsCreating(false);
    }
  }

  async function revokeKey(keyId: string) {
    setError(null);
    setBusyKeyId(keyId);
    try {
      const res = await fetch(`/api/deployments/${deploymentId}/keys/${keyId}`, {
        method: "DELETE",
      });
      const data = await res.json().catch(() => ({})) as { error?: string };
      if (!res.ok) {
        setError(data.error || "Failed to revoke key");
        return;
      }
      setKeys((current) => current.filter((key) => key.id !== keyId));
      setRevealedKeys((current) => current.filter((key) => key.id !== keyId));
    } catch {
      setError("Network error");
    } finally {
      setBusyKeyId(null);
    }
  }

  const activeCount = keys.length;
  const sortedKeys = useMemo(
    () => [...keys].sort((a, b) => Date.parse(a.createdAt) - Date.parse(b.createdAt)),
    [keys]
  );

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-4">
          <div>
            <CardTitle className="flex items-center gap-2 text-base">
              <KeyRound className="h-4 w-4" aria-hidden="true" />
              API Keys
            </CardTitle>
            <CardDescription>
              Manage programmatic access to this Centaur instance.
            </CardDescription>
          </div>
          <Button
            type="button"
            size="sm"
            onClick={createKey}
            disabled={isCreating}
            title="Create new key"
          >
            <Plus className="h-4 w-4" aria-hidden="true" />
            {isCreating ? "Creating" : "Create new key"}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        {error && (
          <div className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm text-destructive">
            {error}
          </div>
        )}

        <div className="flex gap-2">
          <Input
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Key name (optional)"
            aria-label="New key name"
          />
        </div>

        {revealedKeys.length > 0 && (
          <div className="space-y-3 rounded-md border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950 dark:border-amber-900 dark:bg-amber-950/20 dark:text-amber-100">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="font-medium">Copy this key now.</p>
                <p className="mt-1 text-xs opacity-80">
                  You won&apos;t be able to see it again after this panel is dismissed.
                </p>
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setRevealedKeys([])}
                title="Dismiss revealed keys"
              >
                <X className="h-4 w-4" aria-hidden="true" />
              </Button>
            </div>
            {revealedKeys.map((key) => (
              <div
                key={key.id}
                className="flex items-center justify-between gap-3 rounded-md border bg-background px-3 py-2"
              >
                <code className="min-w-0 break-all text-xs text-foreground">
                  {key.key}
                </code>
                <CopyButton text={key.key} />
              </div>
            ))}
          </div>
        )}

        <div className="rounded-md border">
          {sortedKeys.length === 0 ? (
            <div className="px-4 py-5 text-sm text-muted-foreground">
              No active API keys.
            </div>
          ) : (
            sortedKeys.map((key, index) => (
              <div key={key.id}>
                {index > 0 && <Separator />}
                <div className="flex flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
                  <div className="min-w-0 space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <code className="text-sm">{key.keyPrefix}...</code>
                      <Badge variant="outline">{key.name}</Badge>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Created {formatDate(key.createdAt)}
                      {key.lastUsedAt ? ` · Last used ${formatDate(key.lastUsedAt)}` : " · Never used"}
                    </p>
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => revokeKey(key.id)}
                    disabled={activeCount <= 1 || busyKeyId === key.id}
                    title={activeCount <= 1 ? "Create a replacement key first" : "Revoke key"}
                  >
                    <Trash2 className="h-4 w-4" aria-hidden="true" />
                    {busyKeyId === key.id ? "Revoking" : "Revoke"}
                  </Button>
                </div>
              </div>
            ))
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return dateFormatter.format(date);
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      onClick={() => {
        navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      }}
      title="Copy key"
    >
      <Copy className="h-4 w-4" aria-hidden="true" />
      {copied ? "Copied" : "Copy"}
    </Button>
  );
}
