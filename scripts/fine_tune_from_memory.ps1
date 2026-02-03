param(
  [Parameter(Mandatory=$true)][string]$LlamaFactoryPath,
  [string]$OutputJsonl = "",
  [int]$Limit = 2000,
  [switch]$AllowSensitive,
  [switch]$Dedupe
)

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$exportScript = Join-Path $repoRoot "export_ai_memory.py"

if ($OutputJsonl -eq "") {
  $OutputJsonl = Join-Path $LlamaFactoryPath "data\\funpay_ai_memory.jsonl"
}

Write-Host "Exporting memory to $OutputJsonl"
$args = @(
  $exportScript,
  "--out", $OutputJsonl,
  "--limit", $Limit
)
if ($AllowSensitive) { $args += "--allow-sensitive" }
if ($Dedupe) { $args += "--dedupe" }

python $args

Write-Host "Now run your LLaMA-Factory train config (edit dataset to include funpay_ai_memory.jsonl)."
Write-Host "Example:"
Write-Host "  & `"$LlamaFactoryPath\\.venv\\Scripts\\llamafactory-cli.exe`" train <your_train_yaml>"
