terraform {
  required_version = ">= 1.0"
  required_providers {
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
    local = {
      source  = "hashicorp/local"
      version = "~> 2.4"
    }
  }
}

provider "random" {}
provider "local" {}

variable "node_count" {
  default = 3
}

variable "node_ids" {
  default = ["node-a", "node-b", "node-c"]
}

variable "wg_subnet" {
  default = "10.10.0.0/24"
}

variable "artifacts_dir" {
  default = "../artifacts"
}

# Generate WireGuard private keys for each node
resource "random_password" "wg_privkey_a" {
  length  = 44
  special = true
}

resource "random_password" "wg_privkey_b" {
  length  = 44
  special = true
}

resource "random_password" "wg_privkey_c" {
  length  = 44
  special = true
}

# Store keys in files
resource "local_file" "wg_privkey_a" {
  filename        = "${var.artifacts_dir}/node-a.key"
  content         = random_password.wg_privkey_a.result
  file_permission = "0600"
}

resource "local_file" "wg_privkey_b" {
  filename        = "${var.artifacts_dir}/node-b.key"
  content         = random_password.wg_privkey_b.result
  file_permission = "0600"
}

resource "local_file" "wg_privkey_c" {
  filename        = "${var.artifacts_dir}/node-c.key"
  content         = random_password.wg_privkey_c.result
  file_permission = "0600"
}

# Generate WireGuard config for node-a
resource "local_file" "wg_config_a" {
  filename = "${var.artifacts_dir}/node-a.wg"
  content = <<-EOT
# WireGuard config for node-a (PoC)
# NOTE: PSK will be injected by controller via config_agent
# This is a template; actual tunnel IPs and peers are managed by controller.

[Interface]
Address = 10.10.0.2/32
PrivateKey = (set by controller)
ListenPort = 51820

# Peers (node-b and node-c)
[Peer]
PublicKey = (node-b-pubkey)
AllowedIPs = 10.10.0.3/32
PreSharedKey = (injected by controller)

[Peer]
PublicKey = (node-c-pubkey)
AllowedIPs = 10.10.0.4/32
PreSharedKey = (injected by controller)
EOT
}

# Generate WireGuard config for node-b
resource "local_file" "wg_config_b" {
  filename = "${var.artifacts_dir}/node-b.wg"
  content = <<-EOT
# WireGuard config for node-b (PoC)

[Interface]
Address = 10.10.0.3/32
PrivateKey = (set by controller)
ListenPort = 51820

[Peer]
PublicKey = (node-a-pubkey)
AllowedIPs = 10.10.0.2/32
PreSharedKey = (injected by controller)

[Peer]
PublicKey = (node-c-pubkey)
AllowedIPs = 10.10.0.4/32
PreSharedKey = (injected by controller)
EOT
}

# Generate WireGuard config for node-c
resource "local_file" "wg_config_c" {
  filename = "${var.artifacts_dir}/node-c.wg"
  content = <<-EOT
# WireGuard config for node-c (PoC)

[Interface]
Address = 10.10.0.4/32
PrivateKey = (set by controller)
ListenPort = 51820

[Peer]
PublicKey = (node-a-pubkey)
AllowedIPs = 10.10.0.2/32
PreSharedKey = (injected by controller)

[Peer]
PublicKey = (node-b-pubkey)
AllowedIPs = 10.10.0.3/32
PreSharedKey = (injected by controller)
EOT
}

output "artifacts_dir" {
  value = var.artifacts_dir
}

output "wg_configs" {
  value = {
    node-a = local_file.wg_config_a.filename
    node-b = local_file.wg_config_b.filename
    node-c = local_file.wg_config_c.filename
  }
}

output "wg_privkeys" {
  value = {
    node-a = local_file.wg_privkey_a.filename
    node-b = local_file.wg_privkey_b.filename
    node-c = local_file.wg_privkey_c.filename
  }
  sensitive = true
}
