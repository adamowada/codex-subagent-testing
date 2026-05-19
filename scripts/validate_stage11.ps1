param(
    [string]$Config = "configs/initial_experiment.yaml",
    [string]$ExperimentDir = "",
    [string]$Output = "",
    [switch]$RequireCodex,
    [switch]$SkipPreflight,
    [switch]$AllowMissingReport
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")
$Python = if ($env:PYTHON) { $env:PYTHON } else { "python" }

$ArgsList = @(
    "-m", "harness.validation",
    "--repo-root", $RepoRoot.Path,
    "--config", $Config
)

if ($ExperimentDir) {
    $ArgsList += @("--experiment-dir", $ExperimentDir)
}
if ($Output) {
    $ArgsList += @("--output", $Output)
}
if ($RequireCodex) {
    $ArgsList += "--require-codex"
}
if ($SkipPreflight) {
    $ArgsList += "--skip-preflight"
}
if ($AllowMissingReport) {
    $ArgsList += "--allow-missing-report"
}

Push-Location $RepoRoot
try {
    & $Python @ArgsList
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
