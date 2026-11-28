param(
    [string]$Scores = "$PSScriptRoot/../research-reproduction/revision-20261114/results/live-scores.csv"
)

$ErrorActionPreference = 'Stop'
$rows = @(Import-Csv -LiteralPath $Scores)
if ($rows.Count -ne 75 -or @($rows | Where-Object protocol_valid -ne 'True').Count) {
    throw 'Expected 75 protocol-valid primary trials.'
}

function Get-ExactInterval([double[]]$Values) {
    if ($Values.Count -ne 5) { throw 'Expected five trial values.' }
    $means = [double[]]::new(3125)
    for ($i = 0; $i -lt $means.Length; $i++) {
        $code = $i
        $sum = 0.0
        for ($j = 0; $j -lt 5; $j++) {
            $sum += $Values[$code % 5]
            $code = [int][Math]::Floor($code / 5)
        }
        $means[$i] = $sum / 5
    }
    [array]::Sort($means)
    foreach ($q in @(0.025, 0.975)) {
        $position = $q * ($means.Length - 1)
        $lo = [int][Math]::Floor($position)
        $hi = [int][Math]::Ceiling($position)
        $means[$lo] + ($position - $lo) * ($means[$hi] - $means[$lo])
    }
}

$results = foreach ($scenario in ($rows.scenario | Sort-Object -Unique)) {
    $guarded = @($rows | Where-Object { $_.scenario -eq $scenario -and $_.controller -eq 'guarded' } | Sort-Object seed)
    foreach ($policy in @('guarded', 'legacy', 'no_reserve', 'cpu_hpa', 'static')) {
        $reference = @($rows | Where-Object { $_.scenario -eq $scenario -and $_.controller -eq $policy } | Sort-Object seed)
        if ($reference.Count -ne 5 -or ($reference.seed -join ',') -ne ($guarded.seed -join ',') -or
            @($reference.seed | Sort-Object -Unique).Count -ne 5) {
            throw "Invalid seed pairing for $scenario / $policy."
        }
        $rates = @(foreach ($r in $reference) { 100.0 * [double]$r.slo_bad_count / [double]$r.requests })
        $difference = @(for ($i = 0; $i -lt 5; $i++) {
            100.0 * [double]$guarded[$i].slo_bad_count / [double]$guarded[$i].requests - $rates[$i]
        })
        [pscustomobject]@{
            scenario = $scenario
            policy = $policy
            trial_rate_interval = @(Get-ExactInterval $rates)
            paired_difference_interval = @(Get-ExactInterval $difference)
        }
    }
}
$results | ConvertTo-Json -Depth 4
