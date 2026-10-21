# Steward API on ECS Fargate behind an internal ALB. The React UI is served from CloudFront (web.tf).

resource "aws_security_group" "api" {
  name   = "ledgercore-mdm-api-${var.environment}"
  vpc_id = var.vpc_id
}

resource "aws_ecs_cluster" "mdm" {
  name = "ledgercore-mdm-${var.environment}"
}

resource "aws_ecs_task_definition" "api" {
  family                   = "ledgercore-mdm-api-${var.environment}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.environment == "prod" ? 1024 : 512
  memory                   = var.environment == "prod" ? 2048 : 1024
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.api_task.arn

  container_definitions = jsonencode([{
    name  = "api"
    image = "${aws_ecr_repository.api.repository_url}:${var.api_image_tag}"
    portMappings = [{ containerPort = 8000 }]
    environment = [
      { name = "MDM_ENV", value = var.environment },
      { name = "MDM_PUBLISH_BUCKET", value = aws_s3_bucket.publish.bucket },
      { name = "MDM_PUBLISH_PREFIX", value = "golden" },
    ]
    secrets = [
      { name = "MDM_DATABASE_URL", valueFrom = aws_ssm_parameter.database_url.arn },
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.api.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "api"
      }
    }
  }])
}

resource "aws_ecs_service" "api" {
  name            = "ledgercore-mdm-api"
  cluster         = aws_ecs_cluster.mdm.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = var.environment == "prod" ? 3 : 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = var.private_subnet_ids
    security_groups = [aws_security_group.api.id]
  }
}

resource "aws_ecr_repository" "api" {
  name = "ledgercore/mdm-api"
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/ledgercore/mdm/${var.environment}/api"
  retention_in_days = var.environment == "prod" ? 365 : 30
}
