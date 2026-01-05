# WireGuard Configuration Module (PoC)

# This module could be extended to:
# - Generate full WireGuard peer configurations
# - Implement key exchange
# - Support cloud deployments
# - Manage certificate hierarchies

variable "node_id" {
  description = "Node identifier"
  type        = string
}

variable "tunnel_ip" {
  description = "Node's tunnel IP (e.g., 10.10.0.2)"
  type        = string
}

variable "artifact_dir" {
  description = "Output directory for configs"
  type        = string
  default     = "/artifacts"
}

output "wg_config_path" {
  value = "${var.artifact_dir}/${var.node_id}.wg"
}

output "wg_privkey_path" {
  value = "${var.artifact_dir}/${var.node_id}.key"
}
