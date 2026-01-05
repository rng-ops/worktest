.PHONY: demo down logs rotate-now test clean help

help:
	@echo "aligned-meshnet-poc Makefile"
	@echo ""
	@echo "Targets:"
	@echo "  make demo         Start local demo (terraform + docker-compose up)"
	@echo "  make down         Stop and remove containers"
	@echo "  make logs         Tail controller and node logs"
	@echo "  make rotate-now   Force immediate epoch rotation"
	@echo "  make test         Run lightweight controller tests"
	@echo "  make clean        Remove artifacts and reset"
	@echo "  make help         Show this help"

demo: clean
	@echo "[*] Rendering WireGuard configs via Terraform..."
	cd terraform && terraform init
	cd terraform && terraform apply -auto-approve
	@echo "[*] Starting Docker Compose..."
	docker-compose up --build -d
	@echo "[*] Waiting for services to start..."
	sleep 5
	@echo "[+] Demo running! Check logs with: make logs"
	@echo "[+] Force rotation with: make rotate-now"
	@echo "[+] Stop with: make down"

down:
	@echo "[*] Stopping containers..."
	docker-compose down -v 2>/dev/null || true
	@echo "[+] Stopped."

logs:
	@echo "[*] Following logs (Ctrl+C to exit)..."
	docker-compose logs -f controller node-a node-b node-c

rotate-now:
	@echo "[*] Forcing epoch rotation..."
	curl -s -X POST http://localhost:8000/v1/rotate || echo "Controller not running"

test:
	@echo "[*] Running controller tests..."
	cd controller && python -m pytest tests/ -v --tb=short

clean:
	@echo "[*] Cleaning artifacts..."
	rm -rf artifacts/*.wg artifacts/*.key artifacts/*.env artifacts/status.json 2>/dev/null || true
	rm -rf terraform/.terraform terraform/terraform.tfstate* terraform/.terraform.lock.hcl 2>/dev/null || true
	@echo "[+] Cleaned."
