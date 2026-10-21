# Operational store for the steward API. Schema is managed by Alembic (api/alembic), not Terraform.

resource "aws_db_subnet_group" "mdm" {
  name       = "ledgercore-mdm-${var.environment}"
  subnet_ids = var.private_subnet_ids
}

resource "aws_security_group" "rds" {
  name   = "ledgercore-mdm-rds-${var.environment}"
  vpc_id = var.vpc_id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.api.id, aws_security_group.glue.id]
  }
}

resource "aws_db_instance" "mdm" {
  identifier             = "ledgercore-mdm-${var.environment}"
  engine                 = "postgres"
  engine_version         = "15.6"
  instance_class         = var.rds_instance_class
  allocated_storage      = var.rds_allocated_storage_gb
  db_name                = "ledgercore_mdm"
  username               = "mdm_app"
  manage_master_user_password = true
  db_subnet_group_name   = aws_db_subnet_group.mdm.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  multi_az               = var.environment == "prod"
  backup_retention_period = var.environment == "prod" ? 14 : 3
  deletion_protection    = var.environment == "prod"
  skip_final_snapshot    = var.environment != "prod"
  performance_insights_enabled = true
}

resource "aws_ssm_parameter" "database_url" {
  name  = "/ledgercore/mdm/${var.environment}/MDM_DATABASE_URL"
  type  = "SecureString"
  value = "postgresql+psycopg://mdm_app@${aws_db_instance.mdm.address}:5432/ledgercore_mdm"
}
