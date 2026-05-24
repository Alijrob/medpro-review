# Infrastructure — Medical Professionals Review

Terraform/Terragrunt IaC skeleton for the medpro-review AWS infrastructure.

**Status:** Phase 1-B skeleton complete. NOT YET APPLIED to any AWS account.

**Blocker:** DECISIONS.md Entry 003 (AWS account / region / domain) must be resolved before running `terragrunt run-all plan` or `apply`.

---

## Layout

```
src/infrastructure/
  terragrunt.hcl              # Root: S3 remote state, AWS provider generation
  _envcommon/                 # Shared Terragrunt inputs per module (all envs)
    vpc.hcl
    kms.hcl
    s3.hcl
    iam.hcl
    ecr.hcl
    aurora.hcl
    elasticache.hcl
    opensearch.hcl
    eks.hcl
  environments/
    dev/
      env.hcl                 # TODO-Entry-003: account, region, domain placeholders
      vpc/terragrunt.hcl
      kms/terragrunt.hcl
      s3/terragrunt.hcl
      iam/terragrunt.hcl
      ecr/terragrunt.hcl
      aurora/terragrunt.hcl
      elasticache/terragrunt.hcl
      opensearch/terragrunt.hcl
      eks/terragrunt.hcl
    staging/                  # Same layout, HA overrides
    production/               # Same layout, production-scale overrides
  modules/
    vpc/          # VPC, subnets, NAT, IGW, VPC endpoints, flow logs
    kms/          # KMS keys (aurora, redis, s3-reports, s3-audit, opensearch, eks)
    s3/           # Reports bucket, WORM audit bucket (Object Lock), access logs
    iam/          # IRSA roles, audit-writer policy, secrets-read policy
    ecr/          # Container registries (12 services)
    aurora/       # Aurora PostgreSQL 15 + append-only audit DB
    elasticache/  # Redis 7.0 replication group
    opensearch/   # OpenSearch 2.11 domain
    eks/          # EKS cluster, OIDC, managed node groups, add-ons
```

---

## Deploy Order

Modules have dependencies — always apply in this order (Terragrunt handles this automatically via `dependency` blocks):

```
1. kms
2. vpc
3. s3          (depends on: kms)
4. ecr         (no deps)
5. aurora      (depends on: vpc, kms)
6. elasticache (depends on: vpc, kms)
7. opensearch  (depends on: vpc, kms)
8. eks         (depends on: vpc, kms)
9. iam         (depends on: eks, s3)
```

---

## How to Deploy (once Entry 003 is resolved)

### 1. Resolve placeholders in env.hcl

Edit `environments/{env}/env.hcl` and replace every `PLACEHOLDER-*` value:

```hcl
aws_account = "123456789012"
aws_region  = "us-east-1"
domain      = "medprofessionalsreview.com"
```

### 2. Bootstrap remote state (one-time, per environment)

Before the first `terragrunt run-all plan`, the S3 state bucket and DynamoDB lock table must exist. Terragrunt can create them automatically if you set `create_s3_bucket = true` and `create_dynamodb_table = true` in the `remote_state` block — or create them manually:

```bash
aws s3 mb s3://medpro-review-terraform-state-{account}-{region} --region {region}
aws s3api put-bucket-versioning --bucket medpro-review-terraform-state-{account}-{region} \
  --versioning-configuration Status=Enabled
aws dynamodb create-table \
  --table-name medpro-review-terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region {region}
```

### 3. Plan and apply

```bash
# From repo root:
make infra-init ENV=dev
make infra-plan ENV=dev
make infra-apply ENV=dev   # requires explicit approval
```

Or directly with Terragrunt:

```bash
cd src/infrastructure/environments/dev
terragrunt run-all init
terragrunt run-all plan
terragrunt run-all apply
```

---

## Environment Differences

| Setting | dev | staging | production |
|---------|-----|---------|------------|
| NAT Gateways | 1 (single) | 3 (one/AZ) | 3 (one/AZ) |
| EKS API endpoint | public+private | private only | private only |
| Aurora readers | 0 | 1 | 2 |
| Redis nodes | 1 | 2 (replication) | 3 (replication) |
| Aurora deletion protection | off | on | on |
| EKS system nodes | t3.medium x2 | m5.large x3 | m5.large x3 |
| EKS worker nodes | c5.2xlarge | c5.2xlarge | c5.4xlarge |

---

## Key Design Decisions

- **QLDB removed** (DECISIONS.md Entry 005): Aurora append-only tables + S3 Object Lock WORM bucket replace QLDB. Audit immutability enforced at 3 layers: Object Lock COMPLIANCE mode, bucket policy denying DeleteObject, and application-layer INSERT-only role.
- **Zero-Trust networking**: EKS nodes on private subnets. VPC endpoints for ECR, Secrets Manager, S3 — no public internet egress for control-plane traffic. Database subnets isolated (no NAT route).
- **IRSA**: All app pods use IRSA (IAM Roles for Service Accounts) — no EC2 instance profiles or long-lived credentials in pods.
- **KMS**: One key per data type — aurora, elasticache, s3-reports, s3-audit, opensearch, eks-secrets.
- **Immutable ECR tags**: All repositories use `IMAGE_TAG_MUTABILITY = IMMUTABLE` — no image tag overwrites.
