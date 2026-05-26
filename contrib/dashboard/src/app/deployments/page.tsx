import Link from "next/link";
import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";
import { db } from "@/lib/db";
import { deployments } from "@/lib/schema";
import { eq } from "drizzle-orm";

const TIERS: Record<string, { label: string; color: string }> = {
  dev: { label: "Dev", color: "bg-yellow-100 text-yellow-800" },
  small: { label: "Small", color: "bg-blue-100 text-blue-800" },
  prod: { label: "Production", color: "bg-green-100 text-green-800" },
};

function StatusDot({ status }: { status: string }) {
  const colors: Record<string, string> = {
    running: "bg-green-500",
    provisioning: "bg-yellow-500 animate-pulse",
    stopped: "bg-gray-400",
    error: "bg-red-500",
  };
  return (
    <span className="flex items-center gap-2 text-sm">
      <span className={`h-2 w-2 rounded-full ${colors[status] ?? "bg-gray-400"}`} />
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
}

export default async function DeploymentsPage() {
  const { userId } = await auth();
  if (!userId) redirect("/sign-in");

  const rows = await db
    .select()
    .from(deployments)
    .where(eq(deployments.userId, userId))
    .orderBy(deployments.createdAt);

  const hasInProgress = rows.some(
    (d) => d.status === "provisioning" || d.status === "claiming" || d.status === "stopping"
  );

  return (
    <>
      {hasInProgress && <meta httpEquiv="refresh" content="5" />}
    <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Deployments</h1>
          <p className="mt-1 text-sm text-gray-500">
            Each deployment is an isolated Centaur instance on its own cluster.
          </p>
        </div>
        <Link
          href="/deployments/new"
          className="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-700"
        >
          New deployment
        </Link>
      </div>

      {rows.length === 0 ? (
        <div className="rounded-lg border-2 border-dashed border-gray-300 p-12 text-center">
          <h3 className="text-sm font-semibold text-gray-900">
            No deployments
          </h3>
          <p className="mt-1 text-sm text-gray-500">
            Get started by creating a new Centaur deployment.
          </p>
          <Link
            href="/deployments/new"
            className="mt-4 inline-block rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-700"
          >
            Create deployment
          </Link>
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Name
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Tier
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Location
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  IP
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Cost
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {rows.map((d) => {
                const tier = TIERS[d.tier] ?? {
                  label: d.tier,
                  color: "bg-gray-100 text-gray-800",
                };
                return (
                  <tr key={d.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 text-sm font-medium">
                      <Link
                        href={`/deployments/${d.id}`}
                        className="text-gray-900 hover:text-blue-600 hover:underline"
                      >
                        {d.name}
                      </Link>
                    </td>
                    <td className="px-6 py-4">
                      <StatusDot status={d.status} />
                    </td>
                    <td className="px-6 py-4">
                      <span
                        className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${tier.color}`}
                      >
                        {tier.label}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-500">
                      {d.location}
                    </td>
                    <td className="px-6 py-4 font-mono text-sm text-gray-500">
                      {d.ip ?? "—"}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-500">
                      {d.monthlyCost ?? "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
    </>
  );
}
