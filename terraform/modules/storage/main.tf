terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region
}

variable "region" {
  default = "us-east-1"
}

variable "environment" {
  default = "prod"
}

locals {
  common_tags = {
    Project     = "AURA"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

resource "aws_s3_bucket" "aura" {
  bucket = "aura-${var.environment}-storage-${random_string.suffix.result}"

  tags = merge(local.common_tags, {
    Name = "aura-${var.environment}-storage"
  })
}

resource "aws_s3_bucket_versioning" "aura" {
  bucket = aws_s3_bucket.aura.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "aura" {
  bucket = aws_s3_bucket.aura.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "aura" {
  bucket = aws_s3_bucket.aura.id

  rule {
    id     = "log"
    status = "Enabled"

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 90
      storage_class = "GLACIER"
    }

    expiration {
      days = 365
    }
  }
}

resource "random_string" "suffix" {
  length  = 8
  special = false
  upper   = false
}

output "bucket_name" {
  description = "S3 bucket name"
  value       = aws_s3_bucket.aura.id
}

output "bucket_arn" {
  description = "S3 bucket ARN"
  value       = aws_s3_bucket.aura.arn
}
