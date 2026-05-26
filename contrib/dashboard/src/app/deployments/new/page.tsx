"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const TIERS = [
  {
    id: "dev",
    name: "Dev",
    description: "Single node for testing and low-traffic use. No high availability.",
    cost: "~$9/mo",
    specs: "2 vCPU, 4 GB RAM, 80 GB storage",
  },
  {
    id: "small",
    name: "Small Production",
    description: "3-node cluster with dedicated database. Survives single-node failure.",
    cost: "~$82/mo",
    specs: "3 nodes (4 vCPU, 8 GB each) + dedicated Postgres",
  },
  {
    id: "prod",
    name: "Production",
    description: "3-node cluster with larger nodes and burst capacity for heavy workloads.",
    cost: "~$136/mo",
    specs: "3 nodes (8 vCPU, 16 GB each) + dedicated Postgres",
  },
];

const LOCATIONS = [
  { id: "nbg1", name: "Nuremberg, Germany", region: "EU", note: "20 TB/mo traffic included" },
  { id: "fsn1", name: "Falkenstein, Germany", region: "EU", note: "20 TB/mo traffic included" },
  { id: "hel1", name: "Helsinki, Finland", region: "EU", note: "20 TB/mo traffic included" },
  { id: "ash", name: "Ashburn, Virginia", region: "US", note: "1 TB/mo traffic included" },
  { id: "hil", name: "Hillsboro, Oregon", region: "US", note: "1 TB/mo traffic included" },
];

export default function NewDeploymentPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [tier, setTier] = useState("dev");
  const [location, setLocation] = useState("nbg1");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleCreate() {
    if (!name || submitting) return;
    setError(null);
    setSubmitting(true);

    try {
      const res = await fetch("/api/deployments", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, tier, location }),
      });

      if (res.ok) {
        const data = await res.json().catch(() => ({ id: name }));
        router.push(`/deployments/${data.id || name}`);
      } else {
        const data = await res.json().catch(() => ({}));
        setError(data.error || `Failed to create deployment (${res.status})`);
        setSubmitting(false);
      }
    } catch {
      setError("Network error. Please check your connection and try again.");
      setSubmitting(false);
    }
  }

  const selectedLocation = LOCATIONS.find((l) => l.id === location);

  return (
    <div className="mx-auto max-w-2xl px-4 py-10 sm:px-6 lg:px-8">
      <h1 className="text-2xl font-bold tracking-tight mb-2">
        New Deployment
      </h1>
      <p className="text-sm text-gray-500 mb-8">
        Each deployment is an isolated Centaur instance with its own cluster,
        database, and credentials. Provisioning takes 3-5 minutes.
      </p>

      {error && (
        <div className="mb-6 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </div>
      )}

      <div className="space-y-8">
        <div>
          <label
            htmlFor="name"
            className="block text-sm font-medium text-gray-700"
          >
            Deployment name
          </label>
          <input
            id="name"
            type="text"
            required
            autoCapitalize="none"
            autoCorrect="off"
            spellCheck={false}
            value={name}
            onChange={(e) =>
              setName(
                e.target.value
                  .toLowerCase()
                  .replace(/\s+/g, "-")
                  .replace(/[^a-z0-9-]/g, "")
                  .replace(/-{2,}/g, "-")
                  .slice(0, 20)
              )
            }
            placeholder="my-team"
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500"
          />
          <p className="mt-1 text-xs text-gray-500">
            Used to identify this deployment.
          </p>
        </div>

        <fieldset>
          <legend className="text-sm font-medium text-gray-700">
            Choose a plan
          </legend>
          <div className="mt-3 space-y-3">
            {TIERS.map((t) => (
              <label
                key={t.id}
                className={`flex cursor-pointer rounded-lg border p-4 transition-all ${
                  tier === t.id
                    ? "border-gray-900 bg-gray-50 ring-1 ring-gray-900"
                    : "border-gray-200 hover:border-gray-300"
                }`}
              >
                <input
                  type="radio"
                  name="tier"
                  value={t.id}
                  checked={tier === t.id}
                  onChange={() => setTier(t.id)}
                  className="sr-only"
                />
                <div className="flex-1">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-semibold">{t.name}</span>
                    <span className="text-sm font-medium text-gray-900">
                      {t.cost}
                    </span>
                  </div>
                  <p className="mt-1 text-sm text-gray-600">
                    {t.description}
                  </p>
                  <p className="mt-0.5 text-xs text-gray-400">{t.specs}</p>
                </div>
              </label>
            ))}
          </div>
        </fieldset>

        <div>
          <label
            htmlFor="location"
            className="block text-sm font-medium text-gray-700"
          >
            Region
          </label>
          <select
            id="location"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500"
          >
            {LOCATIONS.map((loc) => (
              <option key={loc.id} value={loc.id}>
                {loc.name} ({loc.region})
              </option>
            ))}
          </select>
          {selectedLocation && (
            <p className="mt-1 text-xs text-gray-500">
              {selectedLocation.note}
            </p>
          )}
        </div>

        <div className="flex justify-end gap-3 pt-4 border-t border-gray-200">
          <button
            type="button"
            onClick={() => router.back()}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={submitting || name.length < 2}
            onClick={handleCreate}
            className="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-700 disabled:opacity-50"
          >
            {submitting ? "Creating..." : "Create deployment"}
          </button>
        </div>
      </div>
    </div>
  );
}
