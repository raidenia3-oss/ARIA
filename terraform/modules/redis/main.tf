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

variable "vpc_id" {
  description = "VPC ID"
}

variable "private_subnet_ids" {
  description = "Private subnet IDs"
  type        = list(string)
}

variable "redis_node_size" {
  default = "db.t3.micro"
}

locals {
  common_tags = {
    Project     = "AURA"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

resource "aws_security_group" "redis" {
  name_prefix = "${var.environment}-redis-"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [var.vpc_id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, {
    Name = "${var.environment}-redis-sg"
  })
}

resource "aws_elasticache_subnet_group" "aura" {
  name       = "${var.environment}-aura-redis-subnet"
  subnet_ids = var.private_subnet_ids
}

resource "aws_elasticache_replication_group" "aura" {
  replication_group_id         = "${var.environment}-aura-redis"
  description                  = "AURA Redis cluster"
  engine                       = "redis"
  engine_version               = "7.1"
  node_type                    = var.redis_node_size
  port                         = 6379
  parameter_group_name         = "default.redis7"
  num_cache_clusters           = 2
  automatic_failover_enabled   = true
  multi_az_enabled             = true
  subnet_group_name            = aws_elasticache_subnet_group.aura.name
  security_group_ids           = [aws_security_group.redis.id]
  at_rest_encryption_enabled   = true
  transit_encryption_enabled   = true

  lifecycle {
    ignore_changes = [engine_version]
  }

  tags = merge(local.common_tags, {
    Name = "${var.environment}-aura-redis"
  })
}

output "redis_endpoint" {
  description = "Redis primary endpoint"
  value       = aws_elasticache_replication_group.aura.primary_endpoint_address
}

output "redis_port" {
  description = "Redis port"
  value       = aws_elasticache_replication_group.aura.port
}

output "redis_password" {
  description = "Redis password"
  value       = aws_elasticache_replication_group.aura.auth_token
  sensitive   = true
}
