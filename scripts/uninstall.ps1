# uninstall.ps1 — Quita symlinks de ~/.claude/skills/ que apunten a este repo.
# Solo borra symlinks. Si hay un directorio real con el mismo nombre, lo deja.

$ErrorActionPreference = "Stop"

$RepoDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$SkillsDir = Join-Path $env:USERPROFILE ".claude\skills"

if (-not (Test-Path $SkillsDir)) {
    Write-Host "Nada que desinstalar -- $SkillsDir no existe."
    exit 0
}

$count = 0
Get-ChildItem -Path "$RepoDir\skills" -Directory | ForEach-Object {
    $skillName = $_.Name
    if ($skillName -eq "_template") { return }

    $target = Join-Path $SkillsDir $skillName
    if (-not (Test-Path $target)) { return }

    $item = Get-Item $target -Force
    if ($item.LinkType -eq "SymbolicLink") {
        Remove-Item $target -Force
        Write-Host "  - $skillName (symlink removido)"
        $count++
    } else {
        Write-Host "  ! $skillName existe pero NO es symlink. Se deja por seguridad."
    }
}

Write-Host ""
Write-Host "OK Removed $count skills. El repo queda intacto."
