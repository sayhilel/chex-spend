resource "azurerm_service_plan" "main" {
  name                = local.name
  resource_group_name = local.rg
  location            = local.location
  os_type             = "Linux"
  sku_name            = "FC1"
}

resource "azurerm_function_app_flex_consumption" "main" {
  name                        = local.name
  resource_group_name         = local.rg
  location                    = local.location
  service_plan_id             = azurerm_service_plan.main.id
  storage_container_type      = "blobContainer"
  storage_container_endpoint  = "${azurerm_storage_account.main.primary_blob_endpoint}${azurerm_storage_container.deploy.name}"
  storage_authentication_type = "SystemAssignedIdentity"
  runtime_name                = "python"
  runtime_version             = "3.12"
  maximum_instance_count      = 40
  instance_memory_in_mb       = 512
  https_only                  = true

  identity {
    type = "SystemAssigned"
  }

  app_settings = {
    AzureWebJobsStorage              = ""
    AzureWebJobsStorage__accountName = azurerm_storage_account.main.name
    STORAGE_URL                      = azurerm_storage_account.main.primary_blob_endpoint
  }

  site_config {
    application_insights_connection_string = azurerm_application_insights.main.connection_string
  }
}

resource "azurerm_role_assignment" "function_storage" {
  scope                = azurerm_storage_account.main.id
  role_definition_name = "Storage Blob Data Owner"
  principal_id         = azurerm_function_app_flex_consumption.main.identity[0].principal_id
}
