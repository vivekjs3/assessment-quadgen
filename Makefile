.PHONY: up down status test logs clean help

help:
	@echo "Available commands:"
	@echo "  make up      - Bootstrap KinD cluster, local registry, JCasC, and Jenkins Controller"
	@echo "  make down    - Teardown KinD cluster and local registry"
	@echo "  make status  - Check status of Jenkins and Sample App pods"
	@echo "  make test    - Test sample web application endpoint"
	@echo "  make logs    - View Jenkins controller pod logs"

up:
	@bash scripts/bootstrap.sh

down:
	@bash scripts/teardown.sh

status:
	@kubectl get pods,svc -n jenkins
	@kubectl get pods,svc -n sample-app

test:
	@curl -s -I http://localhost:8081 | head -n 5

logs:
	@kubectl logs -n jenkins -l app.kubernetes.io/name=jenkins -c jenkins --tail=100 -f
