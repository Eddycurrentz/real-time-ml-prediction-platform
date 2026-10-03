# AWS deployment notes

This repository keeps AWS work intentionally limited to deploy documentation and policy scaffolding. No AWS resources are created automatically.

This is a target deployment guide, not evidence of a deployable or tested AWS stack. The current consumer is a stub, Compose does not include MLflow, and neither the local containers nor an AWS deployment have been run. Complete and integration-test those services before using the deployment workflow for a real environment.

## AWS environment

- Intended target: EC2 runs the API, Postgres, and MLflow. Kafka and Spark remain local by architecture decision; the checked-in Compose file does not yet include MLflow or implement model-backed serving.
- Intended target: MLflow artifacts are stored in S3 under a dedicated bucket or prefix such as `rtml-artifacts`.
- GitHub Actions authenticates to AWS with OIDC and pushes images to ECR.
- The EC2 instance profile grants access to ECR pull, S3 artifact write/read, and CloudWatch logs.

## Recommended setup

1. Create an ECR repository for the API image and optionally for the consumer image.
2. Create a protected GitHub `production` environment, restrict it to reviewed deployment branches, and require reviewer approval.
3. Add `POSTGRES_PASSWORD` and `RTML_API_KEY` as environment secrets. Generate separate random URL-safe values of at least 32 characters; never use values from an example file.
4. Add `EC2_HOST_FINGERPRINT` as an environment secret using the EC2 SSH host key fingerprint obtained through a trusted channel.
5. Create an IAM role for GitHub OIDC with the policy in `infrastructure/aws/github-oidc-role-policy.json`.
6. Attach the instance-profile policy in `infrastructure/aws/ec2-instance-profile.json` to the EC2 role.
7. Restrict the instance security group to administrative SSH/SSM and HTTPS through a TLS reverse proxy. Do not allow public ingress to ports 8000, 5432, or 9092.
8. Ensure the EC2 instance can reach ECR, S3, and CloudWatch logs.
9. Complete the missing streaming and model-serving integrations before production use; `/ready` currently verifies configuration only, not that a production model is loaded.

## Cost notes

- Prefer a small EC2 instance with enough RAM for Compose and Postgres.
- Run Spark ETL locally/on demand. The target keeps MLflow with the API and Postgres on EC2 initially, with a future move to dedicated services if the system grows.
- Do not store static AWS credentials in GitHub secrets when OIDC is available.

## Safety

- Deployment scripts are intentionally run only when the user opts in.
- Rollback and cleanup scripts live under `infrastructure/scripts/` and are not executed automatically.
