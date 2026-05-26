# ------------------------------------------------------------------------------
# Centaur customer deployment on Hetzner Cloud
#
# Provisions: private network, firewall, k3s cluster (via cloud-init),
# load balancer, Postgres volume, and deploys the Centaur Helm chart.
# ------------------------------------------------------------------------------

terraform {
  required_version = ">= 1.5"
  required_providers {
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = "~> 1.49"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

provider "hcloud" {
  token = var.hcloud_token
}

# --- Tier defaults ---

locals {
  tier_defaults = {
    dev = {
      join_node_count   = 0
      control_plane_type = "cpx22"   # 2 vCPU, 4 GB — minimal
      postgres_type      = ""
      separate_postgres  = false
    }
    small = {
      join_node_count   = 2
      control_plane_type = "cpx32"   # 4 vCPU, 8 GB
      postgres_type      = "ccx13"   # 2 dedicated vCPU, 8 GB
      separate_postgres  = true
    }
    prod = {
      join_node_count   = 2
      control_plane_type = "cpx42"   # 8 vCPU, 16 GB
      postgres_type      = "ccx23"   # 4 dedicated vCPU, 16 GB
      separate_postgres  = true
    }
  }

  cfg = local.tier_defaults[var.tier]

  control_plane_type = var.control_plane_type != "" ? var.control_plane_type : local.cfg.control_plane_type
  postgres_type      = var.postgres_type != "" ? var.postgres_type : local.cfg.postgres_type

  prefix = "centaur-${var.customer_id}"
}

# --- Networking ---

resource "hcloud_network" "cluster" {
  name     = "${local.prefix}-network"
  ip_range = "10.0.0.0/16"
}

resource "hcloud_network_subnet" "nodes" {
  network_id   = hcloud_network.cluster.id
  type         = "cloud"
  network_zone = var.location == "ash" || var.location == "hil" ? "us-east" : "eu-central"
  ip_range     = "10.0.1.0/24"
}

# --- Firewall ---

resource "hcloud_firewall" "cluster" {
  name = "${local.prefix}-fw"

  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "22"
    source_ips = ["0.0.0.0/0", "::/0"]
  }
  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "6443"
    source_ips = ["0.0.0.0/0", "::/0"]
  }
  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "80"
    source_ips = ["0.0.0.0/0", "::/0"]
  }
  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "443"
    source_ips = ["0.0.0.0/0", "::/0"]
  }
  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "2379-2380"
    source_ips = ["10.0.0.0/16"]
  }
  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "10250"
    source_ips = ["10.0.0.0/16"]
  }
  rule {
    direction  = "in"
    protocol   = "udp"
    port       = "8472"
    source_ips = ["10.0.0.0/16"]
  }

  # Outbound: allow all (required for cloud-init, k3s install, LLM API calls)
  rule {
    direction       = "out"
    protocol        = "tcp"
    port            = "any"
    destination_ips = ["0.0.0.0/0", "::/0"]
  }
  rule {
    direction       = "out"
    protocol        = "udp"
    port            = "any"
    destination_ips = ["0.0.0.0/0", "::/0"]
  }
  rule {
    direction       = "out"
    protocol        = "icmp"
    destination_ips = ["0.0.0.0/0", "::/0"]
  }
}

# --- SSH key ---
# Lookup-or-create: avoids "uniqueness_error" when the same public key is
# registered in the project under a different name.

data "hcloud_ssh_keys" "existing" {}

locals {
  ssh_fingerprint = length(var.ssh_public_keys) > 0 ? md5(var.ssh_public_keys[0]) : ""
  existing_key_id = one([
    for k in data.hcloud_ssh_keys.existing.ssh_keys :
    k.id if k.public_key == var.ssh_public_keys[0]
  ])
}

resource "hcloud_ssh_key" "deploy" {
  count      = length(var.ssh_public_keys) > 0 && local.existing_key_id == null ? 1 : 0
  name       = "${local.prefix}-deploy-${substr(local.ssh_fingerprint, 0, 8)}"
  public_key = var.ssh_public_keys[0]
}

locals {
  ssh_key_ids = length(var.ssh_public_keys) > 0 ? (
    local.existing_key_id != null ? [local.existing_key_id] : [hcloud_ssh_key.deploy[0].id]
  ) : []
}

# --- Generated secrets ---

resource "random_password" "postgres_password" {
  length  = 48
  special = false
}

resource "random_password" "iron_management_key" {
  length  = 64
  special = false
}

resource "random_password" "sandbox_signing_key" {
  length  = 64
  special = false
}

resource "random_password" "slackbot_api_key" {
  length  = 48
  special = false
}

resource "random_password" "k3s_token" {
  length  = 64
  special = false
}

# --- TLS CA for iron-proxy ---

resource "tls_private_key" "ca" {
  algorithm = "RSA"
  rsa_bits  = 4096
}

resource "tls_self_signed_cert" "ca" {
  private_key_pem = tls_private_key.ca.private_key_pem
  subject {
    common_name = "centaur iron-proxy CA"
  }
  validity_period_hours = 87600
  is_ca_certificate     = true
  allowed_uses          = ["cert_signing"]
}

# --- Init node (first control plane, starts the cluster) ---

resource "hcloud_server" "init" {
  name        = "${local.prefix}-cp-0"
  server_type = local.control_plane_type
  location    = var.location
  image       = "ubuntu-24.04"
  ssh_keys    = local.ssh_key_ids
  firewall_ids = [hcloud_firewall.cluster.id]

  network {
    network_id = hcloud_network.cluster.id
  }

  user_data = templatefile("${path.module}/cloud-init.sh.tftpl", {
    k3s_token   = random_password.k3s_token.result
    mode        = "init"
    join_url    = ""
  })

  depends_on = [hcloud_network_subnet.nodes]

  labels = {
    "centaur-customer" = var.customer_id
    "role"             = "control-plane"
  }
}

# --- Join nodes (additional control plane nodes for HA) ---

resource "hcloud_server" "join" {
  count       = local.cfg.join_node_count
  name        = "${local.prefix}-cp-${count.index + 1}"
  server_type = local.control_plane_type
  location    = var.location
  image       = "ubuntu-24.04"
  ssh_keys    = local.ssh_key_ids
  firewall_ids = [hcloud_firewall.cluster.id]

  network {
    network_id = hcloud_network.cluster.id
  }

  user_data = templatefile("${path.module}/cloud-init.sh.tftpl", {
    k3s_token   = random_password.k3s_token.result
    mode        = "join"
    join_url    = "https://${one(hcloud_server.init.network).ip}:6443"
  })

  depends_on = [hcloud_server.init, hcloud_network_subnet.nodes]

  labels = {
    "centaur-customer" = var.customer_id
    "role"             = "control-plane"
  }
}

# --- Postgres node (small/prod tiers) ---

resource "hcloud_server" "postgres" {
  count       = local.cfg.separate_postgres ? 1 : 0
  name        = "${local.prefix}-pg"
  server_type = local.postgres_type
  location    = var.location
  image       = "ubuntu-24.04"
  ssh_keys    = local.ssh_key_ids
  firewall_ids = [hcloud_firewall.cluster.id]

  network {
    network_id = hcloud_network.cluster.id
  }

  user_data = <<-CLOUDINIT
    #!/bin/bash
    set -euo pipefail
    apt-get update -qq
    apt-get install -y -qq postgresql-16
    PG_CONF=/etc/postgresql/16/main/postgresql.conf
    PG_HBA=/etc/postgresql/16/main/pg_hba.conf
    sed -i "s/#listen_addresses = 'localhost'/listen_addresses = '*'/" $PG_CONF
    echo "host ai_v2 tempo 10.0.0.0/16 scram-sha-256" >> $PG_HBA
    systemctl restart postgresql
    sudo -u postgres psql -c "CREATE USER tempo WITH PASSWORD '${random_password.postgres_password.result}';"
    sudo -u postgres psql -c "CREATE DATABASE ai_v2 OWNER tempo;"
  CLOUDINIT

  depends_on = [hcloud_network_subnet.nodes]

  labels = {
    "centaur-customer" = var.customer_id
    "role"             = "postgres"
  }
}

# --- Postgres volume ---

resource "hcloud_volume" "postgres" {
  count    = local.cfg.separate_postgres ? 1 : 0
  name     = "${local.prefix}-pg-data"
  size     = var.tier == "prod" ? 50 : 20
  location = var.location
  format   = "ext4"
}

resource "hcloud_volume_attachment" "postgres" {
  count     = local.cfg.separate_postgres ? 1 : 0
  volume_id = hcloud_volume.postgres[0].id
  server_id = hcloud_server.postgres[0].id
}

# --- Load balancer ---

resource "hcloud_load_balancer" "ingress" {
  name               = "${local.prefix}-lb"
  load_balancer_type = "lb11"
  location           = var.location
  labels = {
    "centaur-customer" = var.customer_id
  }
}

resource "hcloud_load_balancer_network" "ingress" {
  load_balancer_id = hcloud_load_balancer.ingress.id
  network_id       = hcloud_network.cluster.id
}

resource "hcloud_load_balancer_target" "init" {
  type             = "server"
  load_balancer_id = hcloud_load_balancer.ingress.id
  server_id        = hcloud_server.init.id
  use_private_ip   = true
  depends_on       = [hcloud_load_balancer_network.ingress]
}

resource "hcloud_load_balancer_target" "join" {
  count            = local.cfg.join_node_count
  type             = "server"
  load_balancer_id = hcloud_load_balancer.ingress.id
  server_id        = hcloud_server.join[count.index].id
  use_private_ip   = true
  depends_on       = [hcloud_load_balancer_network.ingress]
}

resource "hcloud_load_balancer_service" "https" {
  load_balancer_id = hcloud_load_balancer.ingress.id
  protocol         = "tcp"
  listen_port      = 443
  destination_port = 443
}

resource "hcloud_load_balancer_service" "http" {
  load_balancer_id = hcloud_load_balancer.ingress.id
  protocol         = "tcp"
  listen_port      = 80
  destination_port = 80
}

# --- Computed values for outputs and provision script ---

locals {
  # Dev tier uses the Helm chart's in-cluster Postgres StatefulSet (K8s service name).
  # Small/prod tiers use a dedicated Postgres VM (private IP).
  database_url = "postgresql://tempo:${random_password.postgres_password.result}@${local.cfg.separate_postgres ? one(hcloud_server.postgres[0].network).ip : "centaur-centaur-postgres"}:5432/ai_v2"
}
