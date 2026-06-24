param(
    [string]$Config = "configs/initial_experiment.yaml",
    [int]$Jobs = 1,
    [int]$JudgeJobs = 1,
    [string]$RunsRoot = "runs",
    [string]$ExperimentName = "",
    [string]$StudyId = "",
    [string]$BatchId = "",
    [int]$BatchSequence = 0,
    [string]$BatchStartedAt = "",
    [string]$BatchNotes = "",
    [string]$Resume = "",
    [int]$RepeatFrom = 0,
    [int]$RepeatTo = 0,
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
    "--judge-jobs", "$JudgeJobs",
    "--pilot"
)

if ($ExperimentName) {
    $ArgsList += @("--experiment-name", $ExperimentName)
}
if ($StudyId) {
    $ArgsList += @("--study-id", $StudyId)
}
if ($BatchId) {
    $ArgsList += @("--batch-id", $BatchId)
}
if ($BatchSequence -gt 0) {
    $ArgsList += @("--batch-sequence", "$BatchSequence")
}
if ($BatchStartedAt) {
    $ArgsList += @("--batch-started-at", $BatchStartedAt)
}
if ($BatchNotes) {
    $ArgsList += @("--batch-notes", $BatchNotes)
}
if ($Resume) {
    $ArgsList += @("--resume", $Resume)
}
if ($RepeatFrom -gt 0) {
    $ArgsList += @("--repeat-from", "$RepeatFrom")
}
if ($RepeatTo -gt 0) {
    $ArgsList += @("--repeat-to", "$RepeatTo")
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
