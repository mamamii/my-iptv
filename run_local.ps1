# 本地运行 IPTV 检测并推送更新
# 由 Windows 任务计划定时调用，也可手动执行
$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

git pull --rebase

python -u check.py

if ($LASTEXITCODE -ne 0) {

    # 有效频道数低于保护阈值等原因，放弃本次更新
    exit $LASTEXITCODE

}

git add cleaned.m3u

git diff --cached --quiet

if ($LASTEXITCODE -eq 0) {

    # 无变化
    exit 0

}

git commit -m "update m3u (local)"

git pull --rebase

git push
