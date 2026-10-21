terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
  }
  backend "s3" {
    bucket         = "ledgercore-tfstate"
    key            = "mdm/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "ledgercore-tflock"
  }
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      Application = "ledgercore-mdm"
      Environment = var.environment
      CostCenter  = "600012"
      ManagedBy   = "terraform"
    }
  }
}
