# GitHub Actions assumes this role with OIDC. No long-lived AWS keys.
# The account-wide provider is created once. The role can deploy this stack
# and cannot edit its own trust policy or attach policies to itself.

data "tls_certificate" "github" {
  count = var.create_github_oidc_provider ? 1 : 0
  url   = "https://token.actions.githubusercontent.com"
}

resource "aws_iam_openid_connect_provider" "github" {
  count = var.create_github_oidc_provider ? 1 : 0
  url   = "https://token.actions.githubusercontent.com"

  client_id_list = ["sts.amazonaws.com"]
  thumbprint_list = [
    data.tls_certificate.github[count.index].certificates[0].sha1_fingerprint,
  ]
}

data "aws_caller_identity" "current" {
  count = var.create_github_oidc_role ? 1 : 0
}

data "aws_iam_policy_document" "github_assume" {
  count = var.create_github_oidc_role ? 1 : 0

  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type = "Federated"
      identifiers = [
        var.create_github_oidc_provider
        ? one(aws_iam_openid_connect_provider.github[*].arn)
        : var.github_oidc_provider_arn,
      ]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = [local.github_oidc_subject]
    }
  }
}

data "aws_iam_policy_document" "github_deploy" {
  count = var.create_github_oidc_role ? 1 : 0

  statement {
    sid       = "EcrAuth"
    effect    = "Allow"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    sid    = "EcrRepository"
    effect = "Allow"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:BatchGetImage",
      "ecr:CompleteLayerUpload",
      "ecr:DescribeImages",
      "ecr:DescribeRepositories",
      "ecr:GetDownloadUrlForLayer",
      "ecr:GetLifecyclePolicy",
      "ecr:InitiateLayerUpload",
      "ecr:ListImages",
      "ecr:ListTagsForResource",
      "ecr:PutImage",
      "ecr:PutImageScanningConfiguration",
      "ecr:PutImageTagMutability",
      "ecr:PutLifecyclePolicy",
      "ecr:DeleteLifecyclePolicy",
      "ecr:TagResource",
      "ecr:UntagResource",
      "ecr:UploadLayerPart",
      "ecr:CreateRepository",
      "ecr:DeleteRepository",
    ]
    resources = [
      "arn:aws:ecr:${var.aws_region}:${data.aws_caller_identity.current[count.index].account_id}:repository/${var.project_name}-predict",
    ]
  }

  statement {
    sid    = "LambdaFunction"
    effect = "Allow"
    actions = [
      "lambda:AddPermission",
      "lambda:CreateFunction",
      "lambda:DeleteFunction",
      "lambda:Get*",
      "lambda:List*",
      "lambda:PublishVersion",
      "lambda:RemovePermission",
      "lambda:TagResource",
      "lambda:UntagResource",
      "lambda:Update*",
    ]
    resources = [
      "arn:aws:lambda:${var.aws_region}:${data.aws_caller_identity.current[count.index].account_id}:function:${var.project_name}-predict",
      "arn:aws:lambda:${var.aws_region}:${data.aws_caller_identity.current[count.index].account_id}:function:${var.project_name}-predict:*",
    ]
  }

  statement {
    sid     = "ModelBucket"
    effect  = "Allow"
    actions = ["s3:*"]
    resources = [
      "arn:aws:s3:::${var.project_name}-model-*",
      "arn:aws:s3:::${var.project_name}-model-*/*",
    ]
  }

  statement {
    sid    = "LambdaRole"
    effect = "Allow"
    actions = [
      "iam:CreateRole",
      "iam:DeleteRole",
      "iam:DeleteRolePolicy",
      "iam:GetRole",
      "iam:GetRolePolicy",
      "iam:ListAttachedRolePolicies",
      "iam:ListInstanceProfilesForRole",
      "iam:ListRolePolicies",
      "iam:ListRoleTags",
      "iam:PutRolePolicy",
      "iam:TagRole",
      "iam:UntagRole",
      "iam:UpdateAssumeRolePolicy",
      "iam:UpdateRole",
    ]
    resources = [
      "arn:aws:iam::${data.aws_caller_identity.current[count.index].account_id}:role/${var.project_name}-lambda",
    ]
  }

  statement {
    sid     = "PassLambdaRole"
    effect  = "Allow"
    actions = ["iam:PassRole"]
    resources = [
      "arn:aws:iam::${data.aws_caller_identity.current[count.index].account_id}:role/${var.project_name}-lambda",
    ]

    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["lambda.amazonaws.com"]
    }
  }

  # Read-only on the deploy role itself so plan can refresh it. CI cannot
  # attach a broader policy or change the trust relationship.
  statement {
    sid    = "ReadDeployRole"
    effect = "Allow"
    actions = [
      "iam:GetRole",
      "iam:GetRolePolicy",
      "iam:ListAttachedRolePolicies",
      "iam:ListInstanceProfilesForRole",
      "iam:ListRolePolicies",
      "iam:ListRoleTags",
    ]
    resources = [
      "arn:aws:iam::${data.aws_caller_identity.current[count.index].account_id}:role/${var.project_name}-github-deploy",
    ]
  }

  statement {
    sid    = "ReadGitHubOidcProvider"
    effect = "Allow"
    actions = [
      "iam:GetOpenIDConnectProvider",
      "iam:ListOpenIDConnectProviderTags",
      "iam:TagOpenIDConnectProvider",
      "iam:UntagOpenIDConnectProvider",
      "iam:UpdateOpenIDConnectProviderThumbprint",
    ]
    resources = [
      "arn:aws:iam::${data.aws_caller_identity.current[count.index].account_id}:oidc-provider/token.actions.githubusercontent.com",
    ]
  }

  statement {
    sid    = "ApiGateway"
    effect = "Allow"
    actions = [
      "apigateway:DELETE",
      "apigateway:GET",
      "apigateway:PATCH",
      "apigateway:POST",
      "apigateway:PUT",
      "apigateway:TagResource",
      "apigateway:UntagResource",
    ]
    resources = [
      "arn:aws:apigateway:${var.aws_region}::/apis",
      "arn:aws:apigateway:${var.aws_region}::/apis/*",
      "arn:aws:apigateway:${var.aws_region}::/tags/*",
    ]
  }

  statement {
    sid       = "DescribeLogGroups"
    effect    = "Allow"
    actions   = ["logs:DescribeLogGroups"]
    resources = ["*"]
  }

  statement {
    sid    = "FunctionLogGroup"
    effect = "Allow"
    actions = [
      "logs:CreateLogGroup",
      "logs:DeleteLogGroup",
      "logs:DeleteRetentionPolicy",
      "logs:ListTagsForResource",
      "logs:PutRetentionPolicy",
      "logs:TagResource",
      "logs:UntagResource",
    ]
    resources = [
      "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current[count.index].account_id}:log-group:/aws/lambda/${var.project_name}-predict",
      "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current[count.index].account_id}:log-group:/aws/lambda/${var.project_name}-predict:*",
    ]
  }

  dynamic "statement" {
    for_each = var.terraform_state_bucket_arn == "" ? [] : [var.terraform_state_bucket_arn]
    content {
      sid    = "TerraformStateBucket"
      effect = "Allow"
      actions = [
        "s3:GetBucketVersioning",
        "s3:GetEncryptionConfiguration",
        "s3:ListBucket",
      ]
      resources = [statement.value]
    }
  }

  dynamic "statement" {
    for_each = var.terraform_state_bucket_arn == "" ? [] : [var.terraform_state_bucket_arn]
    content {
      sid    = "TerraformStateObjects"
      effect = "Allow"
      actions = [
        "s3:DeleteObject",
        "s3:GetObject",
        "s3:PutObject",
      ]
      resources = ["${statement.value}/*"]
    }
  }

  dynamic "statement" {
    for_each = var.terraform_lock_table_arn == "" ? [] : [var.terraform_lock_table_arn]
    content {
      sid    = "TerraformLock"
      effect = "Allow"
      actions = [
        "dynamodb:DeleteItem",
        "dynamodb:DescribeTable",
        "dynamodb:GetItem",
        "dynamodb:PutItem",
      ]
      resources = [statement.value]
    }
  }
}

resource "aws_iam_role" "github_deploy" {
  count              = var.create_github_oidc_role ? 1 : 0
  name               = "${var.project_name}-github-deploy"
  assume_role_policy = data.aws_iam_policy_document.github_assume[count.index].json
  description        = "Assumed by GitHub Actions via OIDC to deploy the housing predictor."

  lifecycle {
    precondition {
      condition     = var.create_github_oidc_provider || var.github_oidc_provider_arn != ""
      error_message = "Set create_github_oidc_provider or pass an existing github_oidc_provider_arn."
    }
  }
}

resource "aws_iam_role_policy" "github_deploy" {
  count  = var.create_github_oidc_role ? 1 : 0
  name   = "${var.project_name}-github-deploy"
  role   = aws_iam_role.github_deploy[count.index].id
  policy = data.aws_iam_policy_document.github_deploy[count.index].json
}
