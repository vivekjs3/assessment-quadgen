# Windows PowerShell Teardown Script
$ErrorActionPreference = "Continue"

$ClusterName = "kind-jenkins"
$RegistryName = "kind-registry"

Write-Host "🧹 Tearing down Kubernetes & Jenkins resources..." -ForegroundColor Yellow

kind delete cluster --name $ClusterName
docker stop $RegistryName
docker rm $RegistryName

Write-Host "✅ Teardown complete." -ForegroundColor Green
