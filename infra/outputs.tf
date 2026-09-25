output "function_app_name" {
  value = azurerm_function_app_flex_consumption.main.name
}

output "url" {
  value = "https://${azurerm_function_app_flex_consumption.main.default_hostname}"
}
