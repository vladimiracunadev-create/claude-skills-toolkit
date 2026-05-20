# install.ps1 — Crea symlinks ~/.claude/skills/<skill> → repo/skills/<skill>
# Idempotente. Windows: requiere Developer Mode o ejecución como admin.

$ErrorActionPreference = "Stop"

$RepoDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$SkillsDir = Join-Path $env:USERPROFILE ".claude\skills"

if (-not (Test-Path $SkillsDir)) {
    New-Item -ItemType Directory -Path $SkillsDir -Force | Out-Null
}

Write-Host "Installing skills from $RepoDir\skills"
Write-Host "  Target: $SkillsDir"
Write-Host ""

$count = 0
Get-ChildItem -Path "$RepoDir\skills" -Directory | ForEach-Object {
    $skillName = $_.Name
    if ($skillName -eq "_template") { return }
    $target = Join-Path $SkillsDir $skillName
    if (Test-Path $target) {
        Remove-Item $target -Recurse -Force
    }
    try {
        New-Item -ItemType SymbolicLink -Path $target -Target $_.FullName -Force | Out-Null
        Write-Host "  + $skillName -> $($_.FullName)"
    } catch {
        # Fallback a copia si symlink falla (sin Dev Mode/admin)
        Write-Host "  ! symlink falló ($_), copiando..."
        Copy-Item $_.FullName -Destination $target -Recurse -Force
        Write-Host "  + $skillName (copiado)"
    }
    $count++
}

Write-Host ""
Write-Host "OK Installed $count skills."
Write-Host ""
Write-Host "Verify with:"
Write-Host "  Get-ChildItem $SkillsDir"
