terraform {
  required_version = ">= 1.10"

  required_providers {
    aws     = { source = "hashicorp/aws", version = "~> 6.0" }
    archive = { source = "hashicorp/archive", version = "~> 2.7" }
    random  = { source = "hashicorp/random", version = "~> 3.7" }
  }

  # Remote state in S3 with native S3 locking (no DynamoDB lock table needed).
  # Values come from backend.hcl:  terraform init -backend-config=backend.hcl
  backend "s3" {}
}

provider "aws" {
  region = var.region
  default_tags {
    tags = {
      Project   = var.project
      Owner     = var.owner
      ManagedBy = "terraform"
      Course    = "AICO-mini-capstone"
    }
  }
}

data "aws_caller_identity" "me" {}
data "aws_region" "current" {}

locals {
  name       = "${var.project}-${var.owner}" # e.g. phytro-robby: keeps resources separate in the shared class account
  account_id = data.aws_caller_identity.me.account_id
  region     = data.aws_region.current.region
  # "us.amazon.nova-lite-v1:0" (cross-region inference profile) -> "amazon.nova-lite-v1:0" (foundation model)
  foundation_model_id = replace(var.model_id, "/^(us|eu|apac|global)\\./", "")
  uses_profile        = local.foundation_model_id != var.model_id
}
