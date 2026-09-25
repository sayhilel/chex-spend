resource "azurerm_log_analytics_workspace" "main" {
  name                = local.name
  resource_group_name = local.rg
  location            = local.location
  sku                 = "PerGB2018"
  retention_in_days   = 30
  daily_quota_gb      = 0.1
}

resource "azurerm_application_insights" "main" {
  name                = local.name
  resource_group_name = local.rg
  location            = local.location
  workspace_id        = azurerm_log_analytics_workspace.main.id
  application_type    = "web"
}

resource "azurerm_monitor_action_group" "email" {
  name                = "${local.name}-email"
  resource_group_name = local.rg
  short_name          = "spendcheck"

  email_receiver {
    name          = "owner"
    email_address = var.alert_email
  }
}

resource "azurerm_monitor_metric_alert" "errors" {
  name                = "${local.name}-failed-requests"
  resource_group_name = local.rg
  scopes              = [azurerm_application_insights.main.id]
  severity            = 2
  frequency           = "PT15M"
  window_size         = "PT15M"

  criteria {
    metric_namespace = "microsoft.insights/components"
    metric_name      = "requests/failed"
    aggregation      = "Count"
    operator         = "GreaterThan"
    threshold        = 5
  }

  action {
    action_group_id = azurerm_monitor_action_group.email.id
  }
}

resource "azurerm_consumption_budget_resource_group" "main" {
  name              = "${local.name}-budget"
  resource_group_id = data.azurerm_resource_group.main.id
  amount            = var.monthly_budget
  time_grain        = "Monthly"

  time_period {
    start_date = formatdate("YYYY-MM-01'T'00:00:00Z", timestamp())
  }

  notification {
    operator       = "GreaterThan"
    threshold      = 1
    contact_emails = [var.alert_email]
  }

  notification {
    operator       = "GreaterThan"
    threshold      = 1
    threshold_type = "Forecasted"
    contact_emails = [var.alert_email]
  }

  lifecycle {
    ignore_changes = [time_period]
  }
}
