# Windows PowerShell Native Bootstrap Script
$ErrorActionPreference = "Stop"

$ClusterName = "kind-jenkins"
$RegistryName = "kind-registry"
$RegistryPort = "5001"

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "  🚀 Starting Kubernetes & Jenkins Dynamic CI/CD Setup (Windows)" -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

# 1. Local Container Registry
Write-Host "📦 Checking local container registry '$RegistryName'..." -ForegroundColor Yellow
$regRunning = docker ps --filter "name=$RegistryName" --filter "status=running" -q
if (-not $regRunning) {
    $regExists = docker ps -a --filter "name=$RegistryName" -q
    if ($regExists) {
        docker start $RegistryName | Out-Null
    } else {
        docker run -d --restart=always -p "127.0.0.1:${RegistryPort}:5000" --name "$RegistryName" registry:2 | Out-Null
    }
    Write-Host "✅ Local registry started on port $RegistryPort" -ForegroundColor Green
} else {
    Write-Host "✅ Local registry already running." -ForegroundColor Green
}

# 2. KinD Cluster
Write-Host "☸️ Checking KinD cluster '$ClusterName'..." -ForegroundColor Yellow
$existingClusters = kind get clusters
if ($existingClusters -notcontains $ClusterName) {
    Write-Host "Creating KinD cluster with port mappings & registry support..." -ForegroundColor Yellow
    kind create cluster --name $ClusterName --config kind/kind-config.yaml
} else {
    Write-Host "✅ KinD cluster '$ClusterName' already exists." -ForegroundColor Green
}

# 3. Connect Registry to KinD Network
Write-Host "🔗 Connecting registry to KinD Docker network..." -ForegroundColor Yellow
docker network connect "kind" "$RegistryName" 2>$null | Out-Null

# 4. Apply Namespaces & RBAC
Write-Host "📁 Applying Namespaces & RBAC..." -ForegroundColor Yellow
kubectl apply -f k8s/namespaces.yaml
kubectl apply -f k8s/jenkins-rbac.yaml

# 5. Create JCasC & Plugin ConfigMaps
Write-Host "⚙️ Creating Jenkins JCasC and Plugin ConfigMaps..." -ForegroundColor Yellow
kubectl create configmap jenkins-casc-config --from-file=jenkins.yaml=jcasc/jenkins.yaml -n jenkins --dry-run=client -o yaml | kubectl apply -f -
kubectl create configmap jenkins-plugins-config --from-file=plugins.txt=jcasc/plugins.txt -n jenkins --dry-run=client -o yaml | kubectl apply -f -

# 6. Deploy Jenkins Controller & Services
Write-Host "🚀 Deploying Jenkins Controller & Services..." -ForegroundColor Yellow
kubectl apply -f k8s/jenkins-service.yaml
kubectl apply -f k8s/jenkins-deployment.yaml

Write-Host "⏳ Waiting for Jenkins Controller to become ready (downloading plugins)..." -ForegroundColor Yellow
kubectl rollout status deployment/jenkins -n jenkins --timeout=300s

Write-Host ""
Write-Host "=================================================================" -ForegroundColor Green
Write-Host "  🎉 CI/CD Platform is Ready!" -ForegroundColor Green
Write-Host "=================================================================" -ForegroundColor Green
Write-Host "  Jenkins UI:          http://localhost:8080" -ForegroundColor White
Write-Host "  Default Credentials: admin / adminpassword123" -ForegroundColor White
Write-Host "  Sample App URL:      http://localhost:8081 (after pipeline runs)" -ForegroundColor White
Write-Host "=================================================================" -ForegroundColor Green
