param([string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot))
$ErrorActionPreference='Stop'
$dll='C:\Program Files\Microsoft Power BI Desktop\bin\Microsoft.PowerBI.Tabular.dll'
[void][System.Reflection.Assembly]::LoadFrom($dll)
$modelPath=Join-Path $ProjectRoot 'powerbi\PayerAccess.SemanticModel\definition'
$db=[Microsoft.AnalysisServices.Tabular.TmdlSerializer]::DeserializeDatabaseFromFolder($modelPath)
$receipt=[ordered]@{
  validator='Microsoft.AnalysisServices.Tabular.TmdlSerializer bundled with installed Power BI Desktop'
  status='passed'
  database=$db.Name
  tables=$db.Model.Tables.Count
  relationships=$db.Model.Relationships.Count
  measures=($db.Model.Tables | ForEach-Object {$_.Measures.Count} | Measure-Object -Sum).Sum
  desktopRendered=$false
  daxExecuted=$false
}
$receipt | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $ProjectRoot 'outputs\powerbi-model-validation.json') -Encoding UTF8
$receipt | ConvertTo-Json
