variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "environment" {
  type        = string
  description = "dev | qa | prod"
}

variable "vpc_id" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "rds_instance_class" {
  type    = string
  default = "db.t4g.medium"
}

variable "rds_allocated_storage_gb" {
  type    = number
  default = 50
}

variable "publish_bucket_name" {
  type = string
}

variable "api_image_tag" {
  type = string
}

variable "glue_worker_count" {
  type    = number
  default = 4
}

variable "cost_center_code_width" {
  type        = number
  description = "Width of the ERP cost center code, passed to Glue jobs and the publish notifier"
  default     = 6
}

variable "snowflake_account_url" {
  type = string
}

variable "alert_email" {
  type = string
}
