.PHONY: demo sim build up down clean logs test health fresh seed ui demo-acf handshake registry submission-check

# ── One-command hackathon demo ──────────────────────────────────
demo:
	docker-compose up -d --build
	sleep 15
	python demo.py

# ── Full 22-phase simulation ───────────────────────────────────
sim:
	python simulate_negotiation.py --mode autonomous

# ── 7-step ACF framework demo ─────────────────────────────────
demo-acf:   ## Run 7-step ACF framework demo
	python demo_acf.py

# ── Docker shortcuts ───────────────────────────────────────────
build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

clean:
	docker-compose down -v --remove-orphans

logs:
	docker-compose logs -f api

# ── Tests ──────────────────────────────────────────────────────
test:
	pytest tests/ -v --tb=short

# ── Quick health check ─────────────────────────────────────────
health:
	curl -s http://localhost:8000/health | python -m json.tool

# ── Reset and run fresh demo ───────────────────────────────────
fresh:
	docker-compose down -v
	docker-compose up -d --build
	sleep 15
	python demo.py

# ── Phase 7: Demo UI ──────────────────────────────────────────
seed:
	python scripts/seed_demo_accounts.py

ui:
	python scripts/seed_demo_accounts.py
	@echo "Open http://localhost:8000/ui/login"

# ── Phase 2: Capability Handshake test ────────────────────────
handshake:   ## Test capability handshake endpoint
	curl -s -X POST http://localhost:8000/v1/handshake/ \
	  -H "Content-Type: application/json" \
	  -d '{"buyer_enterprise_id":"test","seller_enterprise_id":"test"}' | python -m json.tool

# ── Phase 2: Agent Registry listing ──────────────────────────
registry:   ## List all registered agents
	curl -s http://localhost:8000/v1/agents/ | python -m json.tool

# ── Phase 4: Full cold-start submission verification ─────────
submission-check:  ## Full cold-start submission verification
	@echo "=== ACF Submission Check ==="
	@echo "1. Health check..."
	@curl -sf http://localhost:8000/health > /dev/null && echo "   ✓ API healthy" || echo "   ✗ API down"
	@echo "2. Framework protocols..."
	@curl -sf http://localhost:8000/v1/framework/protocols | python -m json.tool
	@echo "3. Agent card..."
	@curl -sf http://localhost:8000/.well-known/agent.json | python -m json.tool
	@echo "4. FixedPrice demo..."
	@curl -sf -X POST http://localhost:8000/v1/framework/fixed-price-demo \
	  -H "Content-Type: application/json" \
	  -d '{"fixed_price": 90000, "buyer_budget": 95000}' | python -m json.tool
	@echo "=== All checks passed ==="
