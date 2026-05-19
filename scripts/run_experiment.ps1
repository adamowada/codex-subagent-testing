param(
    [string]$Config = "configs/initial_experiment.yaml",
    [int]$Jobs = 3,
    [int]$JudgeJobs = 2,
    [string]$RunsRoot = "runs",
    [string]$ExperimentName = "",
    [string]$Resume = "",
    [string[]]$RunId = @(),
    [switch]$RerunFailed,
    [switch]$NoReport,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")
$Python = if ($env:PYTHON) { $env:PYTHON } else { "python" }

$ArgsList = @(
    "-m", "harness.orchestrator",
    "--repo-root", $RepoRoot.Path,
    "--config", $Config,
    "--runs-root", $RunsRoot,
    "--jobs", "$Jobs",
    "--judge-jobs", "$JudgeJobs"
)

if ($ExperimentName) {
    $ArgsList += @("--experiment-name", $ExperimentName)
}
if ($Resume) {
    $ArgsList += @("--resume", $Resume)
}
foreach ($Id in $RunId) {
    $ArgsList += @("--run-id", $Id)
}
if ($RerunFailed) {
    $ArgsList += "--rerun-failed"
}
if ($NoReport) {
    $ArgsList += "--no-report"
}
if ($DryRun) {
    $ArgsList += "--dry-run"
}

Push-Location $RepoRoot
try {
    & $Python @ArgsList
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
