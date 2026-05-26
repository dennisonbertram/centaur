output "customer_id" {
  value = var.customer_id
}

output "tier" {
  value = var.tier
}

output "init_node_ip" {
  value = hcloud_server.init.ipv4_address
}

output "init_node_private_ip" {
  value = one(hcloud_server.init.network).ip
}

output "join_node_ips" {
  value = hcloud_server.join[*].ipv4_address
}

output "postgres_ip" {
  value = local.cfg.separate_postgres ? one(hcloud_server.postgres[0].network).ip : "127.0.0.1"
}

output "load_balancer_ip" {
  value = hcloud_load_balancer.ingress.ipv4
}

output "database_url" {
  value     = local.database_url
  sensitive = true
}

output "k3s_token" {
  value     = random_password.k3s_token.result
  sensitive = true
}

output "kubeconfig_command" {
  value = "ssh -o StrictHostKeyChecking=no root@${hcloud_server.init.ipv4_address} cat /etc/rancher/k3s/k3s.yaml | sed 's/127.0.0.1/${hcloud_server.init.ipv4_address}/'"
}

output "postgres_password" {
  value     = random_password.postgres_password.result
  sensitive = true
}

output "iron_management_key" {
  value     = random_password.iron_management_key.result
  sensitive = true
}

output "sandbox_signing_key" {
  value     = random_password.sandbox_signing_key.result
  sensitive = true
}

output "slackbot_api_key" {
  value     = random_password.slackbot_api_key.result
  sensitive = true
}

output "ca_cert_pem" {
  value     = tls_self_signed_cert.ca.cert_pem
  sensitive = true
}

output "ca_key_pem" {
  value     = tls_private_key.ca.private_key_pem
  sensitive = true
}

output "monthly_cost_estimate" {
  value = var.tier == "dev" ? "~€8/month" : var.tier == "small" ? "~€75/month" : "~€125/month"
}
