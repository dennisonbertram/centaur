import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";
import { db } from "@/lib/db";
import { deployments, usageEvents } from "@/lib/schema";
import { eq, sql } from "drizzle-orm";

const TIER_LABELS: Record<string, { label: string; color: string }> = {
  dev: { label: "Dev", color: "bg-yellow-100 text-yellow-800" },
  small: { label: "Small", color: "bg-blue-100 text-blue-800" },
  prod: { label: "Production", color: "bg-green-100 text-green-800" },
};

export default async function UsagePage() {
  const { userId } = await auth();
  if (!userId) redirect("/sign-in");

  const rows = await db
    .select()
    .from(deployments)
    .where(eq(deployments.userId, userId));

  const usage = await db
    .select({
      deploymentId: usageEvents.deploymentId,
      eventType: usageEvents.eventType,
      total: sql<number>`sum(${usageEvents.count})`.as("total"),
    })
    .from(usageEvents)
    .where(
      sql`${usageEvents.deploymentId} IN (SELECT id FROM deployments WHERE user_id = ${userId})`
    )
    .groupBy(usageEvents.deploymentId, usageEvents.eventType);

  const usageByDeployment: Record<string, Record<string, number>> = {};
  for (const row of usage) {
    if (!usageByDeployment[row.deploymentId]) {
      usageByDeployment[row.deploymentId] = {};
    }
    usageByDeployment[row.deploymentId][row.eventType] = Number(row.total);
  }

  const totalTurns = usage
    .filter((u) => u.eventType === "agent_turn")
    .reduce((sum, u) => sum + Number(u.total), 0);
  const totalTools = usage
    .filter((u) => u.eventType === "tool_call")
    .reduce((sum, u) => sum + Number(u.total), 0);

  const now = new Date();
  const monthStart = new Date(now.getFullYear(), now.getMonth(), 1);
  const monthEnd = new Date(now.getFullYear(), now.getMonth() + 1, 0);

  return (
    <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6 lg:px-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight">Usage</h1>
        <p className="mt-1 text-sm text-gray-500">
          {monthStart.toLocaleDateString("en-US", { month: "long", day: "numeric" })}
          {" – "}
          {monthEnd.toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" })}
        </p>
      </div>

      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3 mb-10">
        <div className="rounded-lg border border-gray-200 bg-white p-5">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">
            Deployments
          </p>
          <p className="mt-2 text-2xl font-bold">{rows.length}</p>
          <p className="mt-0.5 text-xs text-gray-400">
            {rows.filter((r) => r.status === "running").length} running
          </p>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-5">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">
            Agent turns
          </p>
          <p className="mt-2 text-2xl font-bold">{totalTurns}</p>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-5">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">
            Tool invocations
          </p>
          <p className="mt-2 text-2xl font-bold">{totalTools}</p>
        </div>
      </div>

      {rows.length === 0 ? (
        <div className="rounded-lg border-2 border-dashed border-gray-300 p-12 text-center">
          <p className="text-sm text-gray-500">
            No deployments yet. Usage data will appear here after you create one.
          </p>
        </div>
      ) : (
        <div className="rounded-lg border border-gray-200 bg-white p-6">
          <h2 className="text-sm font-semibold mb-4">Per-deployment breakdown</h2>
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                <th className="pb-2">Deployment</th>
                <th className="pb-2">Tier</th>
                <th className="pb-2">Status</th>
                <th className="pb-2">Turns</th>
                <th className="pb-2">Tools</th>
                <th className="pb-2 text-right">Cost</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((d) => {
                const tier = TIER_LABELS[d.tier] ?? { label: d.tier, color: "bg-gray-100 text-gray-800" };
                const u = usageByDeployment[d.id] ?? {};
                return (
                  <tr key={d.id} className="border-b border-gray-50">
                    <td className="py-2 font-medium">{d.name}</td>
                    <td className="py-2">
                      <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${tier.color}`}>
                        {tier.label}
                      </span>
                    </td>
                    <td className="py-2 text-sm text-gray-500">{d.status}</td>
                    <td className="py-2">{u.agent_turn ?? 0}</td>
                    <td className="py-2">{u.tool_call ?? 0}</td>
                    <td className="py-2 text-right font-medium">{d.monthlyCost ?? "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
