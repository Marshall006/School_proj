# KODA — raccourcis de developpement.
# `make aide` liste toutes les cibles.

SHELL := /bin/bash
VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
BACKEND := backend

.DEFAULT_GOAL := aide

.PHONY: aide
aide: ## Affiche cette aide
	@echo "KODA — L'ecran se merite."
	@echo
	@grep -hE '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# --- Installation ----------------------------------------------------------

.PHONY: install
install: ## Installe toutes les dependances (API, partage, web, mobile)
	python3 -m venv $(VENV)
	$(PIP) install -q --upgrade pip
	$(PIP) install -q -e "$(BACKEND)[dev]"
	cd shared && npm install --silent && npm run build --silent
	cd web && npm install --silent
	cd mobile && npm install --silent
	@echo "Installation terminee."

.PHONY: install-api
install-api: ## Installe uniquement l'API
	python3 -m venv $(VENV)
	$(PIP) install -q --upgrade pip
	$(PIP) install -q -e "$(BACKEND)[dev]"

# --- Execution -------------------------------------------------------------

.PHONY: api
api: ## Lance l'API en rechargement automatique (port 8000)
	cd $(BACKEND) && ../$(PY) -m uvicorn app.main:app --reload --port 8000

.PHONY: web
web: ## Lance le tableau de bord parent (port 3000)
	cd web && npm run dev

.PHONY: mobile
mobile: ## Lance l'application enfant (Expo)
	cd mobile && npm start

.PHONY: up
up: ## Demarre la pile complete avec Docker
	docker compose up --build

.PHONY: down
down: ## Arrete la pile Docker
	docker compose down

# --- Donnees ---------------------------------------------------------------

.PHONY: seed
seed: ## Remplit la banque pedagogique
	cd $(BACKEND) && ../$(PY) -m app.cli seed

.PHONY: demo
demo: ## Cree le foyer de demonstration (demo@koda.app / demo-koda-2026)
	cd $(BACKEND) && ../$(PY) -m app.cli demo

.PHONY: stats
stats: ## Etat de la banque pedagogique
	cd $(BACKEND) && ../$(PY) -m app.cli stats

.PHONY: migration
migration: ## Genere une migration (make migration m="mon message")
	cd $(BACKEND) && ../$(VENV)/bin/alembic revision --autogenerate -m "$(m)"

.PHONY: migrate
migrate: ## Applique les migrations
	cd $(BACKEND) && ../$(VENV)/bin/alembic upgrade head

# --- Qualite ---------------------------------------------------------------

.PHONY: test
test: ## Lance toute la suite de tests (API + protocole partage)
	cd $(BACKEND) && ../$(PY) -m pytest -q
	cd shared && npm test --silent

.PHONY: test-api
test-api: ## Tests de l'API uniquement
	cd $(BACKEND) && ../$(PY) -m pytest -q

.PHONY: coverage
coverage: ## Tests avec rapport de couverture
	cd $(BACKEND) && ../$(PY) -m pytest -q --cov --cov-report=term-missing:skip-covered

.PHONY: lint
lint: ## Analyse statique
	$(VENV)/bin/ruff check $(BACKEND)/app $(BACKEND)/tests
	cd shared && npm run typecheck --silent

.PHONY: format
format: ## Reformate le code Python
	$(VENV)/bin/ruff format $(BACKEND)/app $(BACKEND)/tests
	$(VENV)/bin/ruff check --fix $(BACKEND)/app $(BACKEND)/tests

.PHONY: typecheck-web
typecheck-web: ## Verifie les types du tableau de bord
	cd web && npm run typecheck

.PHONY: e2e
e2e: ## Parcours navigateur du tableau de bord (API et web doivent tourner)
	cd web && npx playwright install chromium && npm run e2e

.PHONY: integration
integration: ## Boucle serveur <-> tablette hors ligne (l'API doit tourner)
	cd shared && npm run test:integration

.PHONY: verifier
verifier: lint test ## Analyse statique + tests (a lancer avant de livrer)

.PHONY: clean
clean: ## Supprime les artefacts
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name .pytest_cache -prune -exec rm -rf {} +
	rm -rf $(BACKEND)/htmlcov $(BACKEND)/.coverage shared/dist web/.next
