import { logger } from "./logger";

export type ProvisionResult = {
  success: boolean;
  error?: string;
};

export async function provisionDeployment(params: {
  name: string;
  tier: string;
  location: string;
}): Promise<ProvisionResult> {
  // The dashboard doesn't provision directly. It sets status=provisioning
  // in the database, and the provisioner worker service picks it up.
  // This function is a no-op — the worker polls for pending deployments.
  logger.info("provision_requested", {
    id: params.name,
    tier: params.tier,
    location: params.location,
    note: "Provisioner worker will pick this up",
  });
  return { success: true };
}

export async function destroyDeployment(name: string): Promise<ProvisionResult> {
  // Same — the dashboard sets status=stopping, the worker picks it up.
  logger.info("destroy_requested", { id: name });
  return { success: true };
}
