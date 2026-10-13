param(
  [Parameter(Mandatory=$true)][string]$Path,
  [Parameter(Mandatory=$true)][string]$CertificateThumbprint
)
$ErrorActionPreference='Stop'
Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Security') -Force
if($CertificateThumbprint -notmatch '^[A-Fa-f0-9]{40}$'){throw 'Identidade de certificado invalida.'}
$file=(Resolve-Path -LiteralPath $Path).Path
if([IO.Path]::GetExtension($file) -ne '.exe'){throw 'A assinatura exige um EXE.'}
$cert=Get-Item -LiteralPath ('Cert:\CurrentUser\My\'+$CertificateThumbprint)
if(!$cert.HasPrivateKey -or $cert.NotAfter -lt (Get-Date)){throw 'Certificado indisponivel ou vencido.'}
if(!($cert.EnhancedKeyUsageList.ObjectId -contains '1.3.6.1.5.5.7.3.3')){throw 'Certificado nao autoriza assinatura de codigo.'}
$signature=Set-AuthenticodeSignature -LiteralPath $file -Certificate $cert -HashAlgorithm SHA256
if($signature.Status -ne 'Valid'){throw ('Assinatura nao validada: '+$signature.Status)}
Write-Output ('Assinado: '+$signature.SignerCertificate.Subject)
