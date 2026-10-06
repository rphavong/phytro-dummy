variable "project" {
  type    = string
  default = "phytro"
}

variable "owner" {
  description = "Your short name; prefixes every resource so classmates' resources never collide"
  type        = string
  default     = "robby"
}

variable "region" {
  type    = string
  default = "us-east-1"
}

variable "model_id" {
  description = "Bedrock model or inference profile. Nova Lite is one of the cheapest tool-capable models."
  type        = string
  default     = "us.amazon.nova-lite-v1:0"
}

variable "enable_guardrail" {
  description = "Create a Bedrock Guardrail (set false if the class account denies bedrock:CreateGuardrail)"
  type        = bool
  default     = true
}

variable "log_retention_days" {
  type    = number
  default = 7
}

variable "alert_email" {
  description = "Optional: email for the worker-error alarm (you must confirm the SNS subscription)"
  type        = string
  default     = ""
}

variable "off_contact" {
  description = "Contact put in the Open Food Facts User-Agent, as their API terms request"
  type        = string
  default     = "github.com/rphavong"
}
