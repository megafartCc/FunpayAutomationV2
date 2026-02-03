param(
  [Parameter(Mandatory=$true)][string]$LlamaFactoryPath,
  [string]$OutputJsonl = "",
  [int]$Limit = 2000,
  [switch]$AllowSensitive,
  [switch]$Dedupe,
  [string]$TrainYaml = ""
)

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$exportScript = Join-Path $repoRoot "export_ai_memory.py"

if ($OutputJsonl -eq "") {
  $OutputJsonl = Join-Path $LlamaFactoryPath "data\\funpay_ai_memory.jsonl"
}
if ($TrainYaml -eq "") {
  $TrainYaml = Join-Path $LlamaFactoryPath "examples\\train_qlora\\qwen25_coder_7b_qlora_sft_funpay.yaml"
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

$datasetInfo = Join-Path $LlamaFactoryPath "data\\dataset_info.json"
if (Test-Path $datasetInfo) {
  $py = @'
import json
import sys
from pathlib import Path
path = Path(sys.argv[1])
data = json.loads(path.read_text(encoding="utf-8"))
if "funpay_ai_memory" not in data:
    data["funpay_ai_memory"] = {
        "file_name": "funpay_ai_memory.jsonl",
        "formatting": "sharegpt",
        "columns": {"messages": "conversations"},
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
'@
  $py | python - $datasetInfo
}

Write-Host "Now run LLaMA-Factory training:"
Write-Host "  & `"$LlamaFactoryPath\\.venv\\Scripts\\llamafactory-cli.exe`" train `"$TrainYaml`""
