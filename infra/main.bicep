// Rules Lawyer infrastructure: ACR, Postgres (pgvector), Container Apps (api + ui), monitoring.
// Deploy into an existing resource group:
//   az deployment group what-if -g <rg> -f infra/main.bicep -p postgresAdminPassword=... anthropicApiKey=...
//   az deployment group create  -g <rg> -f infra/main.bicep -p postgresAdminPassword=... anthropicApiKey=...
// Apps are created with a placeholder image; the CD workflow pushes real images and swaps them in.

@description('Short prefix for all resource names; must be globally unique-ish for ACR.')
param namePrefix string = 'ruleslawyer'

@description('Azure region for every resource.')
param location string = resourceGroup().location

@description('Postgres admin username.')
param postgresAdminUser string = 'ruleslawyer'

@secure()
@description('Postgres admin password (pass on the CLI, never commit).')
param postgresAdminPassword string

@secure()
@description('Anthropic API key, stored as a Container Apps secret.')
param anthropicApiKey string

@description('API image ref; the placeholder is replaced by the CD workflow after first build.')
param apiImage string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

@description('UI image ref; the placeholder is replaced by the CD workflow after first build.')
param uiImage string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

var acrName = toLower(replace('${namePrefix}acr', '-', ''))
var acrPullRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')

// ---- monitoring: Log Analytics + workspace-based App Insights ----
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${namePrefix}-logs'
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: '${namePrefix}-insights'
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
  }
}

// ---- container registry (managed-identity pull, no admin creds) ----
resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: acrName
  location: location
  sku: { name: 'Basic' }
  properties: {
    adminUserEnabled: false
  }
}

// ---- Postgres Flexible Server (Burstable) + pgvector + database ----
resource postgres 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' = {
  name: '${namePrefix}-pg'
  location: location
  sku: { name: 'Standard_B1ms', tier: 'Burstable' }
  properties: {
    version: '16'
    administratorLogin: postgresAdminUser
    administratorLoginPassword: postgresAdminPassword
    storage: { storageSizeGB: 32 }
    backup: { backupRetentionDays: 7, geoRedundantBackup: 'Disabled' }
    highAvailability: { mode: 'Disabled' }
    network: { publicNetworkAccess: 'Enabled' }
    authConfig: { activeDirectoryAuth: 'Disabled', passwordAuth: 'Enabled' }
  }
}

// allowlist pgvector so 001_schema.sql's CREATE EXTENSION vector succeeds
resource pgExtensions 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2024-08-01' = {
  parent: postgres
  name: 'azure.extensions'
  properties: { value: 'VECTOR', source: 'user-override' }
}

// let Azure-hosted services (the container apps) reach the server
resource pgFirewallAzure 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2024-08-01' = {
  parent: postgres
  name: 'AllowAzureServices'
  properties: { startIpAddress: '0.0.0.0', endIpAddress: '0.0.0.0' }
}

resource pgDatabase 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2024-08-01' = {
  parent: postgres
  name: 'ruleslawyer'
  dependsOn: [pgExtensions]
}

// ---- Container Apps environment wired to Log Analytics ----
resource env 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: '${namePrefix}-env'
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

// ---- api: FastAPI, scale-to-zero, secrets for DB + LLM, App Insights connection string ----
resource apiApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${namePrefix}-api'
  location: location
  identity: { type: 'SystemAssigned' }
  properties: {
    managedEnvironmentId: env.id
    configuration: {
      ingress: { external: true, targetPort: 8000, transport: 'auto' }
      secrets: [
        { name: 'database-url', value: 'postgresql://${postgresAdminUser}:${postgresAdminPassword}@${postgres.properties.fullyQualifiedDomainName}:5432/ruleslawyer?sslmode=require' }
        { name: 'anthropic-api-key', value: anthropicApiKey }
      ]
    }
    template: {
      containers: [
        {
          name: 'api'
          image: apiImage
          resources: { cpu: json('1.0'), memory: '2Gi' }
          env: [
            { name: 'DATABASE_URL', secretRef: 'database-url' }
            { name: 'ANTHROPIC_API_KEY', secretRef: 'anthropic-api-key' }
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsights.properties.ConnectionString }
          ]
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 2
        rules: [ { name: 'http', http: { metadata: { concurrentRequests: '10' } } } ]
      }
    }
  }
}

// ---- ui: Streamlit, scale-to-zero, points at the api's public FQDN ----
resource uiApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${namePrefix}-ui'
  location: location
  identity: { type: 'SystemAssigned' }
  properties: {
    managedEnvironmentId: env.id
    configuration: {
      ingress: { external: true, targetPort: 8501, transport: 'auto' }
    }
    template: {
      containers: [
        {
          name: 'ui'
          image: uiImage
          resources: { cpu: json('0.5'), memory: '1Gi' }
          env: [
            { name: 'RULESLAWYER_API_URL', value: 'https://${apiApp.properties.configuration.ingress.fqdn}' }
          ]
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 2
        rules: [ { name: 'http', http: { metadata: { concurrentRequests: '10' } } } ]
      }
    }
  }
}

// ---- let each app pull from ACR with its managed identity (no stored registry creds) ----
resource apiAcrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, apiApp.id, 'AcrPull')
  scope: acr
  properties: {
    principalId: apiApp.identity.principalId
    roleDefinitionId: acrPullRoleId
    principalType: 'ServicePrincipal'
  }
}

resource uiAcrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, uiApp.id, 'AcrPull')
  scope: acr
  properties: {
    principalId: uiApp.identity.principalId
    roleDefinitionId: acrPullRoleId
    principalType: 'ServicePrincipal'
  }
}

output acrLoginServer string = acr.properties.loginServer
output acrName string = acr.name
output apiAppName string = apiApp.name
output uiAppName string = uiApp.name
output apiFqdn string = apiApp.properties.configuration.ingress.fqdn
output uiFqdn string = uiApp.properties.configuration.ingress.fqdn
output postgresFqdn string = postgres.properties.fullyQualifiedDomainName
