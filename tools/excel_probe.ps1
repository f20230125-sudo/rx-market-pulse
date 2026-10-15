param([string]$Path, [string]$Out)
$ErrorActionPreference = 'Stop'
$xl = New-Object -ComObject Excel.Application
$xl.Visible = $false
$xl.DisplayAlerts = $false
try {
  $wb = $xl.Workbooks.Open($Path)
  $inp = $wb.Worksheets.Item('Inputs'); $sc = $wb.Worksheets.Item('Scorecard'); $chk = $wb.Worksheets.Item('Checks'); $sum = $wb.Worksheets.Item('Summary')
  $scenarios = @(
    @{ id='S1'; area='All areas'; year=2025; look=3; scen='Balanced';   growth=0.08; ta=10; tb=20; neut='Yes' },
    @{ id='S2'; area='Diabetes & obesity'; year=2025; look=3; scen='Growth-led'; growth=0.08; ta=10; tb=20; neut='Yes' },
    @{ id='S3'; area='Oncology'; year=2023; look=2; scen='Size-led'; growth=0.05; ta=8; tb=15; neut='Yes' },
    @{ id='S4'; area='Rare & genetic disease'; year=2024; look=1; scen='Balanced'; growth=0.12; ta=10; tb=20; neut='Yes' },
    @{ id='S5'; area='All areas'; year=2025; look=3; scen='Balanced'; growth=0.08; ta=10; tb=20; neut='No' },
    @{ id='S6'; area='Immunology & inflammation'; year=2025; look=4; scen='Growth-led'; growth=0.10; ta=12; tb=18; neut='Yes' }
  )
  $result = @()
  foreach ($s in $scenarios) {
    $inp.Range('C5').Value2 = $s.area
    $inp.Range('C6').Value2 = [double]$s.year
    $inp.Range('C7').Value2 = [double]$s.look
    $inp.Range('C22').Value2 = $s.scen
    $inp.Range('C11').Value2 = [double]$s.growth
    $inp.Range('C12').Value2 = [double]$s.ta
    $inp.Range('C13').Value2 = [double]$s.tb
    $inp.Range('C30').Value2 = $s.neut
    $wb.Application.CalculateFull()
    $rows = @()
    $vals = $sc.Range('A7:X57').Value2
    for ($i = 1; $i -le 51; $i++) {
      $rows += ,@($vals[$i,1], $vals[$i,4], $vals[$i,5], $vals[$i,6], $vals[$i,7], $vals[$i,8], $vals[$i,9], $vals[$i,10], $vals[$i,11], $vals[$i,12], $vals[$i,13], $vals[$i,14], $vals[$i,15], $vals[$i,16], $vals[$i,17], $vals[$i,19], $vals[$i,21], $vals[$i,22], $vals[$i,23], $vals[$i,24])
    }
    $checks = @(); foreach ($r in 5..11) { $checks += [string]$chk.Cells.Item($r,5).Value2 }
    $top = @(); foreach ($r in 5..14) { $top += [string]$sum.Cells.Item($r,3).Value2 }
    $result += [pscustomobject]@{ id=$s.id; inputs=$s; rows=$rows; checks=$checks; overall=[string]$chk.Range('C13').Value2; top10=$top;
        coverage=[double]$inp.Range('C27').Value2; headline1=[string]$sum.Range('B18').Value2; headline2=[string]$sum.Range('B19').Value2; headline3=[string]$sum.Range('B20').Value2 }
  }
  $result | ConvertTo-Json -Depth 6 -Compress | Set-Content -Path $Out -Encoding UTF8
  $wb.Close($false)
  "ok"
} finally { $xl.Quit(); [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($xl) }
