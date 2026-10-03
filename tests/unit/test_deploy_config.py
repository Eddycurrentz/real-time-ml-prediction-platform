from __future__ import annotations

from pathlib import Path

import yaml


def test_compose_and_github_workflows_parse_as_yaml() -> None:
    documents = [
        Path("docker-compose.yml"),
        Path(".github/workflows/ci.yml"),
        Path(".github/workflows/deploy.yml"),
        Path(".github/dependabot.yml"),
    ]

    for document in documents:
        assert yaml.safe_load(document.read_text(encoding="utf-8"))


def test_compose_supports_remote_images_for_deployment() -> None:
    compose_text = Path("docker-compose.yml").read_text(encoding="utf-8")

    assert "API_IMAGE" in compose_text
    assert "CONSUMER_IMAGE" in compose_text
    assert "image: ${API_IMAGE:-rtml-api:local}" in compose_text
    assert "image: ${CONSUMER_IMAGE:-rtml-consumer:local}" in compose_text


def test_compose_uses_required_secrets_and_private_host_bindings() -> None:
    compose_text = Path("docker-compose.yml").read_text(encoding="utf-8")

    assert "POSTGRES_PASSWORD: rtml" not in compose_text
    assert "${POSTGRES_PASSWORD:?" in compose_text
    assert "${RTML_API_KEY:?" in compose_text
    assert "127.0.0.1" in compose_text
    assert "internal: true" in compose_text
    assert "no-new-privileges:true" in compose_text


def test_deploy_workflow_exists() -> None:
    workflow = Path(".github/workflows/deploy.yml")

    assert workflow.exists()
    assert "aws-actions/configure-aws-credentials" in workflow.read_text(encoding="utf-8")


def test_deployment_workflow_fails_closed_and_runs_tests_before_aws_auth() -> None:
    workflow = Path(".github/workflows/deploy.yml").read_text(encoding="utf-8")

    assert "POSTGRES_PASSWORD: rtml" not in workflow
    assert '"5432:5432"' not in workflow
    assert '"8000:8000"' not in workflow
    assert "RTML_API_KEY: $RTML_API_KEY" in workflow
    assert "EC2_HOST_FINGERPRINT" in workflow
    assert "fingerprint: ${{ secrets.EC2_HOST_FINGERPRINT }}" in workflow
    assert "pip-audit --progress-spinner off" in workflow
    assert "if: ${{ secrets.POSTGRES_PASSWORD != '' && secrets.RTML_API_KEY != ''" in workflow
    assert "secrets.EC2_HOST_FINGERPRINT != ''" in workflow
    assert workflow.index("Test before deployment") < workflow.index("Configure AWS credentials")
    assert "${ECR_REPOSITORY_API}:latest" not in workflow
