variable "region" {
  description = "AWS region (Tokyo for this project)"
  type        = string
  default     = "ap-northeast-1"
}

variable "account_id" {
  description = "AWS account id — used to make the S3 bucket name globally unique"
  type        = string
}
