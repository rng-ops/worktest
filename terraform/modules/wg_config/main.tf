# WireGuard configuration template (minimal for PoC)

variable "node_id" {
  description = "Node identifier"
  type        = string
}

variable "tunnel_ip" {
  description = "Tunnel IP for this node"
  type        = string
}

variable "peers" {
  description = "List of peer node_ids"
  type        = list(string)
  default     = []
}

variable "artifact_dir" {
  type    = string
  default = "/artifacts"
}
