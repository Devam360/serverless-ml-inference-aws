resource "aws_apigatewayv2_api" "http" {
  name          = "${var.project_name}-http"
  protocol_type = "HTTP"
  description   = "California housing prediction API"

  cors_configuration {
    allow_headers = ["content-type"]
    allow_methods = ["GET", "POST"]
    allow_origins = ["*"]
    max_age       = 600
  }
}

resource "aws_apigatewayv2_integration" "lambda" {
  api_id                 = aws_apigatewayv2_api.http.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.predict.invoke_arn
  integration_method     = "POST"
  payload_format_version = "2.0"
  timeout_milliseconds   = 30000
}

resource "aws_apigatewayv2_route" "health" {
  api_id    = aws_apigatewayv2_api.http.id
  route_key = "GET /health"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_apigatewayv2_route" "predict" {
  api_id    = aws_apigatewayv2_api.http.id
  route_key = "POST /predict"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.http.id
  name        = "$default"
  auto_deploy = true
  description = "Default stage with a low throttle for a public demo."

  default_route_settings {
    throttling_burst_limit = var.api_throttle_burst
    throttling_rate_limit  = var.api_throttle_rate
  }
}

resource "aws_lambda_permission" "health" {
  statement_id  = "AllowAPIGatewayHealth"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.predict.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http.execution_arn}/*/GET/health"
}

resource "aws_lambda_permission" "predict" {
  statement_id  = "AllowAPIGatewayPredict"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.predict.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http.execution_arn}/*/POST/predict"
}
