terraform {
  required_version = ">= 1.6"
}

variable "replicas" {
  type    = number
  default = 2
}

resource "terraform_data" "app_config" {
  input = {
    name     = "shop"
    replicas = var.replicas
    image    = "registry.example.com/shop:1.4.2"
  }
}

resource "terraform_data" "orders_db" {
  input = {
    engine  = "postgres"
    version = "16"
    size_gb = 50
  }
}

output "app_config" {
  value = terraform_data.app_config.output
}
