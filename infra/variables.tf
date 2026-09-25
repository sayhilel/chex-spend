variable "resource_group_name" {
  type    = string
  default = "rg-spending-checkup"
}

variable "alert_email" {
  type      = string
  sensitive = true
}

variable "monthly_budget" {
  type    = number
  default = 1
}
