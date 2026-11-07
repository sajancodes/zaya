$desktopPath = [System.Environment]::GetFolderPath('Desktop')
$shortcutPath = Join-Path $desktopPath "Zaya.lnk"

$repoRoot = (Get-Item -Path ".").FullName
$targetPath = Join-Path $repoRoot ".venv\Scripts\pythonw.exe"
$iconPath = Join-Path $repoRoot "config\zaya.ico"

$wshShell = New-Object -ComObject WScript.Shell
$shortcut = $wshShell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $targetPath
$shortcut.Arguments = "main.pyw"
$shortcut.WorkingDirectory = $repoRoot
$shortcut.IconLocation = "$iconPath,0"
$shortcut.Description = "Zaya AI Assistant - Developed by Sajan Rai"
$shortcut.Save()

Write-Output "Shortcut successfully created at: $shortcutPath"
