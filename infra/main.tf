locals {
  model_artifact_path = "${path.module}/../artifacts/model.joblib"
  github_oidc_subject = (
    var.github_oidc_subject != ""
    ? var.github_oidc_subject
    : "repo:${var.github_repository}:ref:refs/heads/main"
  )
}
