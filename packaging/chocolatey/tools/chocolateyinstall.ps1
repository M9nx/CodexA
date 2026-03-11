$ErrorActionPreference = 'Stop'

$toolsDir = "$(Split-Path -Parent $MyInvocation.MyCommand.Definition)"
$url = "https://github.com/m9nx/codexa/releases/download/v0.5.0/codexa-windows-x86_64.zip"

Install-ChocolateyZipPackage -PackageName 'codexa' `
  -Url64bit $url `
  -UnzipLocation $toolsDir
