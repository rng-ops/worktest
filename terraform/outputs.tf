# Terraform outputs

output "artifacts_directory" {
  description = "Path to artifacts directory"
  value       = var.artifacts_dir
}

output "wireguard_configs" {
  description = "Paths to generated WireGuard configs"
  value = {
    node_a = local_file.wg_config_a.filename
    node_b = local_file.wg_config_b.filename
    node_c = local_file.wg_config_c.filename
  }
}

output "wireguard_private_keys" {
  description = "Paths to generated WireGuard private keys (base64-encoded)"
  value = {
    node_a = local_file.wg_privkey_a.filename
    node_b = local_file.wg_privkey_b.filename
    node_c = local_file.wg_privkey_c.filename
  }
  sensitive = true
}

output "next_steps" {
  description = "Next steps to run the demo"
  value = [
    "1. cd .. && docker-compose build",
    "2. docker-compose up -d",
    "3. docker-compose logs -f"
  ]
}
