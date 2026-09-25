resource "azurerm_storage_account" "main" {
  name                            = replace(local.name, "-", "")
  resource_group_name             = local.rg
  location                        = local.location
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  min_tls_version                 = "TLS1_2"
  shared_access_key_enabled       = false
  allow_nested_items_to_be_public = false
  default_to_oauth_authentication = true
}

resource "azurerm_storage_container" "uploads" {
  name               = "uploads"
  storage_account_id = azurerm_storage_account.main.id
}

resource "azurerm_storage_container" "reports" {
  name               = "reports"
  storage_account_id = azurerm_storage_account.main.id
}

resource "azurerm_storage_container" "deploy" {
  name               = "deploy"
  storage_account_id = azurerm_storage_account.main.id
}

resource "azurerm_storage_management_policy" "expire" {
  storage_account_id = azurerm_storage_account.main.id

  rule {
    name    = "delete-after-7-days"
    enabled = true
    filters {
      prefix_match = ["uploads/", "reports/"]
      blob_types   = ["blockBlob"]
    }
    actions {
      base_blob {
        delete_after_days_since_modification_greater_than = 7
      }
    }
  }
}
