# Terraform README

## Overview

This Terraform configuration renders WireGuard configurations and keys to the `artifacts/` directory.

For the PoC, we use the local provider to generate files without cloud dependencies.

## Usage

```bash
cd terraform
terraform init
terraform apply
```

This generates:
- `../artifacts/node-a.wg`, `node-b.wg`, `node-c.wg` – WireGuard configs
- `../artifacts/node-a.key`, `node-b.key`, `node-c.key` – Private keys

## Future Work

- **Cloud Provisioning:** Add AWS, GCP, Azure modules to provision nodes on actual cloud infrastructure
- **Key Exchange:** Implement automated key distribution and rotation
- **Networking:** Define VPCs, subnets, firewall rules per cloud provider
- **Monitoring:** Integrate with cloud observability stacks

## Integration with Docker Compose

The `docker-compose.yml` mounts `artifacts/` into containers as read-only, allowing Docker to use configs rendered by Terraform.

```yaml
volumes:
  - ./artifacts:/artifacts:ro
```
