output "api_base_url" {
  description = "HTTP API invoke URL. Routes are /health and /predict."
  value       = trimsuffix(aws_apigatewayv2_stage.default.invoke_url, "/")
}

output "health_url" {
  description = "GET this URL for a model-loaded check and the holdout metrics stored in the artifact."
  value       = "${trimsuffix(aws_apigatewayv2_stage.default.invoke_url, "/")}/health"
}

output "predict_url" {
  description = "POST a JSON feature object to this URL."
  value       = "${trimsuffix(aws_apigatewayv2_stage.default.invoke_url, "/")}/predict"
}

output "model_bucket_name" {
  description = "Private bucket that holds the joblib artifact."
  value       = aws_s3_bucket.model.bucket
}

output "model_s3_key" {
  description = "Object key of the artifact the function loads on cold start."
  value       = aws_s3_object.model.key
}

output "ecr_repository_url" {
  description = "Push the Lambda image here before apply."
  value       = aws_ecr_repository.lambda.repository_url
}

output "lambda_function_name" {
  description = "Prediction function name."
  value       = aws_lambda_function.predict.function_name
}

output "github_deploy_role_arn" {
  description = "Set GitHub secret AWS_ROLE_ARN to this value after the bootstrap apply. Null when the role is not created."
  value       = one(aws_iam_role.github_deploy[*].arn)
}
