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

variable "vpc_cidr" {
  default = "10.0.0.0/16"
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

resource "aws_vpc" "aura" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = merge(local.common_tags, {
    Name = "aura-vpc"
  })
}

resource "aws_subnet" "private" {
  count = 3

  vpc_id            = aws_vpc.aura.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, count.index + 1)
  availability_zone = data.aws_availability_zones.available.names[count.index]

  tags = merge(local.common_tags, {
    Name = "aura-private-${count.index + 1}"
    Tier = "private"
  })
}

resource "aws_subnet" "public" {
  count = 3

  vpc_id            = aws_vpc.aura.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, count.index + 101)
  availability_zone = data.aws_availability_zones.available.names[count.index]

  map_public_ip_on_launch = true

  tags = merge(local.common_tags, {
    Name = "aura-public-${count.index + 1}"
    Tier = "public"
  })
}

resource "aws_internet_gateway" "aura" {
  vpc_id = aws_vpc.aura.id

  tags = merge(local.common_tags, {
    Name = "aura-igw"
  })
}

resource "aws_eip" "nat" {
  count = 3

  domain = "vpc"
  depends_on = [aws_internet_gateway.aura]

  tags = merge(local.common_tags, {
    Name = "aura-nat-eip-${count.index + 1}"
  })
}

resource "aws_nat_gateway" "aura" {
  count = 3

  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id

  tags = merge(local.common_tags, {
    Name = "aura-nat-${count.index + 1}"
  })
}

resource "aws_route_table" "private" {
  count = 3

  vpc_id = aws_vpc.aura.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.aura[count.index].id
  }

  tags = merge(local.common_tags, {
    Name = "aura-private-rt-${count.index + 1}"
  })
}

resource "aws_route_table_association" "private" {
  count = 3

  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private[count.index].id
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.aura.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.aura.id
  }

  tags = merge(local.common_tags, {
    Name = "aura-public-rt"
  })
}

resource "aws_route_table_association" "public" {
  count = 3

  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

data "aws_availability_zones" "available" {}
