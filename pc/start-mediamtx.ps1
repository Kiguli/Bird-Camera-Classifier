# Starts the Windows-hosted RTSP server for the prototype.
# If a Windows Security Alert pops up on first run, click "Allow access" -
# the Frigate container reaches this server through the WSL2 virtual network.
# NOTE: keep this file pure ASCII - PowerShell 5.1 misparses UTF-8 punctuation.
& "$PSScriptRoot\mediamtx\mediamtx.exe" "$PSScriptRoot\mediamtx\mediamtx-win.yml"
