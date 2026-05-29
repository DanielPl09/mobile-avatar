# Vital Eval Launcher
#
#   .\run.ps1 bot              start the Telegram bot
#   .\run.ps1 sim              simulate all 4 personas (single session)
#   .\run.ps1 sim arc          simulate full arcs (all sessions)
#   .\run.ps1 safety           run all 19 safety probes → reports/safety_report.md
#   .\run.ps1 report           alignment report → reports/alignment_report.md
#   .\run.ps1 all              sim arc + safety + report
#   .\run.ps1 setup            create missing Telegram topics (first-time setup)

$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
$cmd = $args[0]
$sub = $args[1]

function Run($script, $extra = "") {
    $full = "python `"$ROOT\$script`" $extra"
    Write-Host "`n> $full`n" -ForegroundColor Cyan
    Invoke-Expression $full
}

switch ($cmd) {
    "bot" { Run "bot.py" }

    "sim" {
        if ($sub -eq "arc") {
            Run "simulate_patient.py" "-p all --arc"
        } else {
            Run "simulate_patient.py" "-p all"
        }
    }

    "safety" {
        $filter = if ($sub) { "-p $sub" } else { "-p all" }
        Run "simulate_patient.py" "--safety $filter"
        Run "report_safety.py" "--out `"$ROOT\reports\safety_report.md`""
        Write-Host "`nSaved -> $ROOT\reports\safety_report.md" -ForegroundColor Green
    }

    "report" {
        Run "report_alignment.py" "--out `"$ROOT\reports\alignment_report.md`" --limit 80"
        Write-Host "`nSaved -> $ROOT\reports\alignment_report.md" -ForegroundColor Green
    }

    "all" {
        Run "clear_topics.py"
        Run "simulate_patient.py" "-p all --arc"
        Run "simulate_patient.py" "--safety -p all"
        Run "report_alignment.py" "--out `"$ROOT\reports\alignment_report.md`" --limit 80"
        Run "report_safety.py" "--out `"$ROOT\reports\safety_report.md`""
        Write-Host "`nDone. Reports in $ROOT\reports\" -ForegroundColor Green
    }

    "setup" {
        Run "setup_topics.py"
    }

    default {
        Write-Host @"

  .\run.ps1 bot           start the bot (separate terminal)
  .\run.ps1 sim           simulate all 4 personas (single session)
  .\run.ps1 sim arc       full multi-session arc (3-5 sessions each)
  .\run.ps1 safety        all 19 safety probes  -> reports/safety_report.md
  .\run.ps1 report        alignment report      -> reports/alignment_report.md
  .\run.ps1 all           clear + sim arc + safety + report
  .\run.ps1 setup         create missing Telegram topics (first-time setup)

  Personas: svetlana (T2D elderly), shira (mum-of-3), ahmad (adversarial), avraham (GLP-1)
  Topics:   30=Svetlana  566=Shira  11=Ahmad  1016=Avraham

"@ -ForegroundColor Yellow
    }
}
