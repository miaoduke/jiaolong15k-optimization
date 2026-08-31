# =============================================================
#  00_git_init_safety.ps1  —  蛟龙15K优化方案 仓库安全初始化
#  用途: 在正式 git init / git add 之前验证 .gitignore 覆盖，
#        防止 _private_不上传（含脱敏前口令备份）整库误提交。
#  用法: 安装 git 后, 在该目录运行  powershell -ExecutionPolicy Bypass -File .\00_git_init_safety.ps1
# =============================================================
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"

Write-Host "== 0) 检查 git 是否可用 ==" -ForegroundColor Cyan
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "  [!] 未找到 git。请先安装 git 后重试。" -ForegroundColor Yellow
    exit 1
}
Write-Host "  [OK] git: $(git --version)"

Write-Host "== 1) 检查是否已存在 .git 仓库 ==" -ForegroundColor Cyan
if (Test-Path ".\.git") {
    Write-Host "  [!] 已存在 .git，跳过 init（仍执行覆盖校验，见步骤3）" -ForegroundColor Yellow
} else {
    Write-Host "  执行 git init ..."
    git init
    Write-Host "  [OK] git init 完成" -ForegroundColor Green
}

Write-Host "== 2) 统计 .gitignore 应忽略的私有文件数 ==" -ForegroundColor Cyan
$privRoot = "_private_不上传"
if (Test-Path $privRoot) {
    $privCount = (Get-ChildItem $privRoot -Recurse -File | Measure-Object).Count
    Write-Host "  私有目录文件总数: $privCount"
}

Write-Host "== 3) 逐一校验私有文件是否被 .gitignore 覆盖(关键安全门) ==" -ForegroundColor Cyan
$leaked = @()
Get-ChildItem -LiteralPath $privRoot -Recurse -File -ErrorAction SilentlyContinue | ForEach-Object {
    $rel = $_.FullName.Substring((Get-Location).Path.Length + 1)
    $ignored = git check-ignore -q -- $rel
    if ($LASTEXITCODE -ne 0) {
        $leaked += $rel
    }
}
if ($leaked.Count -eq 0) {
    Write-Host "  [OK] 私有目录全部被 .gitignore 覆盖，未发现泄漏文件" -ForegroundColor Green
} else {
    Write-Host "  [!!!] 以下 $($leaked.Count) 个私有文件未被忽略，严禁 git add -A 前必须先处理:" -ForegroundColor Red
    $leaked | ForEach-Object { Write-Host "      $_" }
    exit 2
}

Write-Host "== 4) 预演 git status, 检查待暂存文件是否混入敏感产物 ==" -ForegroundColor Cyan
git status --short | Select-Object -First 40
Write-Host ""
Write-Host "== 5) 关键产物抽查 ==" -ForegroundColor Cyan
foreach ($pat in @("*__pycache__*", "*.pyc", "*.log")) {
    $hits = git ls-files --others --exclude-standard | Where-Object { $_ -like $pat }
    if ($hits) {
        Write-Host "  [!] 发现应忽略但未忽略的 $pat : $($hits.Count) 项" -ForegroundColor Yellow
        $hits | Select-Object -First 5 | ForEach-Object { Write-Host "      $_" }
    } else {
        Write-Host "  [OK] $pat 无泄漏" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "== 安全门通过。现在可以人工执行:  git add <选定文件>  (切勿使用 git add -A 一次性提交全部) ==" -ForegroundColor Green