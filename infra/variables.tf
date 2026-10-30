variable "aws_region" {
  description = "Region for the Lambda function, HTTP API, logs, and ECR repository."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Short prefix for resource names. Lowercase, used in the S3 bucket prefix."
  type        = string
  default     = "housing-predictor"

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]{1,28}[a-z0-9]$", var.project_name))
    error_message = "project_name must be 3-30 characters: lowercase letters, digits, and hyphens, starting and ending with a letter or digit."
  }
}

variable "lambda_image_uri" {
  description = "ECR image URI including the tag. The default is a placeholder so terraform validate runs without an image; apply rejects it."
  type        = string
  default     = "000000000000.dkr.ecr.us-east-1.amazonaws.com/housing-predictor-predict:placeholder"
}

variable "model_s3_key" {
  description = "Object key for the joblib artifact uploaded from artifacts/model.joblib."
  type        = string
  default     = "models/california-housing/model.joblib"

  validation {
    condition     = length(var.model_s3_key) > 3 && !startswith(var.model_s3_key, "/")
    error_message = "model_s3_key must be a non-empty key without a leading slash."
  }
}

variable "lambda_memory_mb" {
  description = "Lambda memory. CPU scales with memory; 1024 MB keeps the scikit-learn cold start inside the API Gateway timeout."
  type        = number
  default     = 1024

  validation {
    condition     = var.lambda_memory_mb >= 128 && var.lambda_memory_mb <= 10240
    error_message = "lambda_memory_mb must be between 128 and 10240."
  }
}

variable "lambda_timeout_seconds" {
  description = "Lambda timeout. HTTP API integrations cap at 30 seconds, so a higher value would not help callers."
  type        = number
  default     = 30

  validation {
    condition     = var.lambda_timeout_seconds >= 3 && var.lambda_timeout_seconds <= 30
    error_message = "lambda_timeout_seconds must be between 3 and 30."
  }
}

variable "log_retention_days" {
  description = "CloudWatch log retention. Fourteen days is enough for a demo and limits storage cost."
  type        = number
  default     = 14

  validation {
    condition = contains([
      1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731,
      1096, 1827, 2192, 2557, 2922, 3288, 3653
    ], var.log_retention_days)
    error_message = "log_retention_days must be a CloudWatch Logs retention value."
  }
}

variable "api_throttle_rate" {
  description = "Steady-state requests per second for the HTTP API. Caps the bill on a public demo endpoint."
  type        = number
  default     = 10
}

variable "api_throttle_burst" {
  description = "Burst limit for the HTTP API stage."
  type        = number
  default     = 20
}

variable "force_destroy_model_bucket" {
  description = "When true, terraform destroy deletes the model bucket even if it still holds the artifact. The artifact is also in git."
  type        = bool
  default     = true
}

variable "github_repository" {
  description = "GitHub repository allowed to assume the deploy role, in owner/name form."
  type        = string
  default     = "Devam360/serverless-ml-inference-aws"

  validation {
    condition     = can(regex("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", var.github_repository))
    error_message = "github_repository must look like owner/name."
  }
}

variable "github_oidc_subject" {
  description = "OIDC sub claim trusted by the deploy role. Empty means only workflow runs from refs/heads/main."
  type        = string
  default     = ""
}

variable "create_github_oidc_provider" {
  description = "Create the account-wide GitHub OIDC provider. Turn on for the admin bootstrap apply. The deploy workflow passes true so later applies keep the provider."
  type        = bool
  default     = false
}

variable "create_github_oidc_role" {
  description = "Create the GitHub Actions deploy role. Same lifecycle as create_github_oidc_provider."
  type        = bool
  default     = false
}

variable "github_oidc_provider_arn" {
  description = "Existing GitHub OIDC provider ARN, used when create_github_oidc_provider is false and create_github_oidc_role is true."
  type        = string
  default     = ""
}

variable "terraform_state_bucket_arn" {
  description = "State bucket ARN the deploy role may read and write. Empty leaves state access off the role. Pass the same value on every apply."
  type        = string
  default     = ""
}

variable "terraform_lock_table_arn" {
  description = "Optional DynamoDB lock table ARN for the deploy role. Empty skips lock permissions."
  type        = string
  default     = ""
}
