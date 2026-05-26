# Hetzner Project Pool

Hetzner Cloud does not support project creation via API. Each customer
deployment needs its own project for isolation. Pre-create a pool of empty
projects so the provisioning script can assign them on demand.

## Setup (one-time, manual)

1. Go to [console.hetzner.cloud](https://console.hetzner.cloud)
2. Create 10 projects named `centaur-pool-01` through `centaur-pool-10`
3. For each project, generate a read/write API token under Security > API Tokens
4. Store the tokens in a file (one per line, `project_name:token`):

```
centaur-pool-01:SCN5h4fDbh...
centaur-pool-02:ABC1234567...
...
```

Save as `~/.centaur/project-pool.txt` (or set `CENTAUR_PROJECT_POOL_FILE`).

## How the provisioning script uses it

When `provision.sh create` is called without `HCLOUD_TOKEN` set, it:
1. Reads the pool file
2. Finds the first project not already assigned (checks `~/.centaur/deployments/`)
3. Uses that project's token for the deployment
4. Records the assignment in `~/.centaur/deployments/<customer>/project.txt`

When `provision.sh destroy` is called, the project is released back to the pool.

## Scaling the pool

When the pool runs low (<3 remaining), the provisioning script prints a
warning. Create more projects in the console as needed. There is no hard
limit on projects per Hetzner account.

## Alternative: single-project, namespace isolation

For internal/staging use where full project isolation isn't needed, you can
run all customer deployments in a single Hetzner project using separate k3s
clusters (different server names, networks, and firewalls). Set
`HCLOUD_TOKEN` directly — the pool file is not required.
