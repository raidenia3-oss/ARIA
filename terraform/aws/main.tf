provider "aws" {
  region = var.aws_region
}

terraform {
  backend "s3" {}
}

variable "aws_region" {
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

module "networking" {
  source     = "./modules/networking"
  region     = var.aws_region
  vpc_cidr   = "10.0.0.0/16"
  environment = var.environment
}

module "kubernetes" {
  source             = "./modules/kubernetes"
  region             = var.aws_region
  cluster_name       = "aura-${var.environment}"
  cluster_version    = "1.28"
  vpc_id             = module.networking.vpc_id
  private_subnet_ids = module.networking.private_subnet_ids
  public_subnet_ids  = module.networking.public_subnet_ids
  node_instance_type = "t3.large"
  min_nodes          = 3
  max_nodes          = 10
  environment        = var.environment
  depends_on         = [module.networking]
}

module "redis" {
  source            = "./modules/redis"
  region            = var.aws_region
  environment       = var.environment
  vpc_id            = module.networking.vpc_id
  private_subnet_ids = module.networking.private_subnet_ids
  redis_node_size   = "db.t3.micro"
}

module "storage" {
  source      = "./modules/storage"
  region      = var.aws_region
  environment = var.environment
}
