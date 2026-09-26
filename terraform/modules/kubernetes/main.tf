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

variable "cluster_name" {
  default = "aura-prod"
}

variable "cluster_version" {
  default = "1.28"
}

variable "vpc_id" {
  description = "VPC ID"
}

variable "private_subnet_ids" {
  description = "Private subnet IDs"
  type        = list(string)
}

variable "public_subnet_ids" {
  description = "Public subnet IDs"
  type        = list(string)
}

variable "node_instance_type" {
  default = "t3.large"
}

variable "min_nodes" {
  default = 3
}

variable "max_nodes" {
  default = 10
}

locals {
  common_tags = {
    Project     = "AURA"
    Environment = "prod"
    ManagedBy   = "Terraform"
  }
}

resource "aws_eks_cluster" "aura" {
  name     = var.cluster_name
  version  = var.cluster_version
  role_arn = aws_iam_role.eks_cluster.arn

  vpc_config {
    subnet_ids                   = concat(var.private_subnet_ids, var.public_subnet_ids)
    endpoint_private_access      = true
    endpoint_public_access       = true
    public_access_cidrs          = ["0.0.0.0/0"]
    security_group_ids           = [aws_security_group.eks_cluster.id]
  }

  depends_on = [
    aws_iam_role_policy_attachment.eks_cluster_policy,
    aws_iam_role_policy_attachment.eks_vpc_resource_controller,
  ]

  tags = merge(local.common_tags, {
    Name = var.cluster_name
  })
}

resource "aws_eks_node_group" "aura_nodes" {
  cluster_name    = aws_eks_cluster.aura.name
  node_group_name = "aura-nodes"
  node_role_arn   = aws_iam_role.eks_nodes.arn
  subnet_ids      = var.private_subnet_ids
  instance_types  = [var.node_instance_type]

  scaling_config {
    desired_size = var.min_nodes
    max_size     = var.max_nodes
    min_size     = var.min_nodes
  }

  update_config {
    max_unavailable = 1
  }

  depends_on = [
    aws_iam_role_policy_attachment.eks_worker_node_policy,
    aws_iam_role_policy_attachment.eks_cni_policy,
    aws_iam_role_policy_attachment.eks_container_registry_policy,
  ]

  tags = merge(local.common_tags, {
    Name = "aura-node-group"
  })
}

resource "aws_security_group" "eks_cluster" {
  name_prefix = "${var.cluster_name}-cluster-"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, {
    Name = "${var.cluster_name}-cluster-sg"
  })
}

resource "aws_iam_role" "eks_cluster" {
  name_prefix = "${var.cluster_name}-cluster-"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "eks.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "eks_cluster_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
  role       = aws_iam_role.eks_cluster.name
}

resource "aws_iam_role_policy_attachment" "eks_vpc_resource_controller" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSVPCResourceController"
  role       = aws_iam_role.eks_cluster.name
}

resource "aws_iam_role" "eks_nodes" {
  name_prefix = "${var.cluster_name}-nodes-"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "eks_worker_node_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
  role       = aws_iam_role.eks_nodes.name
}

resource "aws_iam_role_policy_attachment" "eks_cni_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
  role       = aws_iam_role.eks_nodes.name
}

resource "aws_iam_role_policy_attachment" "eks_container_registry_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
  role       = aws_iam_role.eks_nodes.name
}

resource "aws_eks_addon" "vpc_cni" {
  cluster_name = aws_eks_cluster.aura.name
  addon_name   = "vpc-cni"
}

resource "aws_eks_addon" "coredns" {
  cluster_name = aws_eks_cluster.aura.name
  addon_name   = "coredns"
}

resource "aws_eks_addon" "kube_proxy" {
  cluster_name = aws_eks_cluster.aura.name
  addon_name   = "kube-proxy"
}

data "aws_eks_cluster" "aura" {
  name = aws_eks_cluster.aura.name
}

data "aws_eks_cluster_auth" "aura" {
  name = aws_eks_cluster.aura.name
}

provider "kubernetes" {
  host                   = data.aws_eks_cluster.aura.endpoint
  cluster_ca_certificate = base64decode(data.aws_eks_cluster.aura.certificate_authority[0].data)
  token                  = data.aws_eks_cluster_auth.aura.token
}

resource "kubernetes_namespace" "aura" {
  metadata {
    name = "aura"
    labels = {
      "app.kubernetes.io/managed-by" = "Terraform"
    }
  }
}

resource "helm_release" "ingress_nginx" {
  name       = "ingress-nginx"
  repository = "https://kubernetes.github.io/ingress-nginx"
  chart      = "ingress-nginx"
  namespace  = "ingress-nginx"
  version    = "4.8.0"

  create_namespace = true

  values = [
    yamlencode({
      controller = {
        replicaCount = 3
        service = {
          type = "LoadBalancer"
        }
        metrics = {
          enabled = true
        }
      }
    })
  ]
}

resource "helm_release" "cert_manager" {
  name       = "cert-manager"
  repository = "https://charts.jetstack.io"
  chart      = "cert-manager"
  namespace  = "cert-manager"
  version    = "v1.13.0"

  create_namespace = true

  set {
    name  = "installCRDs"
    value = "true"
  }
}

output "kubeconfig" {
  description = "Kubeconfig for the EKS cluster"
  value       = aws_eks_cluster.aura.endpoint
  sensitive   = true
}

output "cluster_name" {
  description = "EKS cluster name"
  value       = aws_eks_cluster.aura.name
}
