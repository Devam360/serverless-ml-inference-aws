resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${var.project_name}-predict"
  retention_in_days = var.log_retention_days
}

resource "aws_ecr_repository" "lambda" {
  name                 = "${var.project_name}-predict"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }
}

resource "aws_ecr_lifecycle_policy" "lambda" {
  repository = aws_ecr_repository.lambda.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep the five most recent images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 5
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

resource "aws_lambda_function" "predict" {
  function_name = "${var.project_name}-predict"
  role          = aws_iam_role.lambda.arn
  package_type  = "Image"
  image_uri     = var.lambda_image_uri
  timeout       = var.lambda_timeout_seconds
  memory_size   = var.lambda_memory_mb
  architectures = ["x86_64"]
  description   = "Scores one California housing block group from the S3 artifact."

  environment {
    variables = {
      MODEL_BUCKET = aws_s3_bucket.model.bucket
      MODEL_KEY    = var.model_s3_key
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.lambda,
    aws_iam_role_policy.lambda,
    aws_s3_object.model,
  ]

  lifecycle {
    precondition {
      condition     = !strcontains(var.lambda_image_uri, "000000000000.dkr.ecr.")
      error_message = "lambda_image_uri still uses the 000000000000 placeholder. Push an image to ECR and pass its URI. The placeholder exists so terraform validate can run without an image."
    }
  }
}
