<#
  medir-wifi.ps1 - Registra la calidad de la conexion a internet en un CSV.

  Que mide en cada ronda (unos 60-90 segundos):
    - Datos del wifi: red, punto de acceso (BSSID), senal %, banda, canal, velocidad de enlace
    - Ping al router/punto de acceso (calidad del enlace wifi)
    - Ping a internet (1.1.1.1 y 8.8.8.8): latencia, jitter y perdida de paquetes
    - Tiempo de resolucion DNS
    - Velocidad de bajada contra 2 servidores distintos (Cloudflare y OVH)
    - Velocidad de subida (Cloudflare)
    - Tiempo de respuesta de webs reales (PRADO, UGR, GitHub, PyPI, Google, Wikipedia)

  Uso normal: doble clic en iniciar-medicion.bat (mide cada 15 min hasta que cierres la ventana).
  Prueba suelta: doble clic en prueba-rapida.bat (una sola medicion con el lugar que indiques).

  No necesita permisos de administrador ni instalar nada.
#>
param(
    [string]$Lugar = "habitacion",
    [int]$IntervaloMin = 15,
    [switch]$UnaVez,
    [int]$MaxMBDescarga = 20,
    [int]$MaxSegDescarga = 12,
    [string]$Salida = ""
)

$ErrorActionPreference = "Continue"
$inv = [Globalization.CultureInfo]::InvariantCulture
if (-not $Salida) { $Salida = Join-Path $PSScriptRoot "datos\mediciones.csv" }
$carpeta = Split-Path $Salida -Parent
if (-not (Test-Path $carpeta)) { New-Item -ItemType Directory -Path $carpeta | Out-Null }

try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
} catch {}
Add-Type -AssemblyName System.Net.Http

# Evita que el portatil entre en suspension mientras el script esta abierto
# (no impide que se suspenda al cerrar la tapa).
try {
    Add-Type -Namespace MedirWifi -Name Energia -MemberDefinition @'
[DllImport("kernel32.dll")]
public static extern uint SetThreadExecutionState(uint esFlags);
'@
    [void][MedirWifi.Energia]::SetThreadExecutionState([uint32]"0x80000001")
} catch {}

function F($x, [int]$d = 2) {
    if ($null -eq $x -or ($x -is [string] -and $x -eq "")) { return "" }
    return ([double]$x).ToString("F$d", $inv)
}

function Nuevo-Cliente {
    $h = [System.Net.Http.HttpClientHandler]::new()
    $h.AllowAutoRedirect = $true
    $c = [System.Net.Http.HttpClient]::new($h)
    $c.Timeout = [TimeSpan]::FromSeconds(40)
    $c.DefaultRequestHeaders.UserAgent.ParseAdd("Mozilla/5.0 (Windows NT 10.0; Win64; x64) medir-wifi/1.0")
    return $c
}

function Medir-Ping([string]$destino, [int]$n = 20) {
    $r = [ordered]@{ media = $null; jitter = $null; max = $null; perdida = $null }
    if (-not $destino) { return $r }
    $p = [System.Net.NetworkInformation.Ping]::new()
    $t = New-Object System.Collections.Generic.List[double]
    $perdidos = 0
    for ($i = 0; $i -lt $n; $i++) {
        try {
            $resp = $p.Send($destino, 1000)
            if ($resp.Status -eq [System.Net.NetworkInformation.IPStatus]::Success) { $t.Add([double]$resp.RoundtripTime) }
            else { $perdidos++ }
        } catch { $perdidos++ }
        Start-Sleep -Milliseconds 150
    }
    $p.Dispose()
    $r.perdida = 100.0 * $perdidos / $n
    if ($t.Count -gt 0) {
        $r.media = ($t | Measure-Object -Average).Average
        $r.max = ($t | Measure-Object -Maximum).Maximum
        if ($t.Count -gt 1) {
            $dif = 0.0
            for ($i = 1; $i -lt $t.Count; $i++) { $dif += [math]::Abs($t[$i] - $t[$i - 1]) }
            $r.jitter = $dif / ($t.Count - 1)
        } else { $r.jitter = 0 }
    }
    return $r
}

function Medir-Descarga($cliente, [string]$url) {
    # Descarga durante un maximo de $MaxSegDescarga segundos o $MaxMBDescarga MB.
    # La velocidad se calcula desde el primer byte (no incluye el tiempo de conexion).
    $res = [ordered]@{ mbps = $null; mb = $null; error = "" }
    $resp = $null; $stream = $null
    try {
        $resp = $cliente.GetAsync($url, [System.Net.Http.HttpCompletionOption]::ResponseHeadersRead).GetAwaiter().GetResult()
        if (-not $resp.IsSuccessStatusCode) { $res.error = "HTTP $([int]$resp.StatusCode)"; return $res }
        $stream = $resp.Content.ReadAsStreamAsync().GetAwaiter().GetResult()
        $buf = New-Object byte[] 65536
        $total = 0L
        $limite = [long]$MaxMBDescarga * 1MB
        $sw = [Diagnostics.Stopwatch]::StartNew()
        while ($true) {
            $tarea = $stream.ReadAsync($buf, 0, $buf.Length)
            if (-not $tarea.Wait(10000)) { $res.error = "sin datos 10 s"; break }
            $n = $tarea.Result
            if ($n -le 0) { break }
            $total += $n
            if ($total -ge $limite -or $sw.Elapsed.TotalSeconds -ge $MaxSegDescarga) { break }
        }
        $seg = $sw.Elapsed.TotalSeconds
        if ($total -gt 0 -and $seg -gt 0) {
            $res.mbps = ($total * 8 / 1e6) / $seg
            $res.mb = $total / 1MB
        }
    } catch {
        $res.error = ($_.Exception.GetBaseException().Message -replace '[\r\n,;]', ' ')
    } finally {
        if ($stream) { $stream.Dispose() }
        if ($resp) { $resp.Dispose() }
    }
    return $res
}

function Medir-Subida($cliente) {
    # Primero 1 MB; si va rapido, repite con 5 MB para medir mejor.
    $res = [ordered]@{ mbps = $null; error = "" }
    foreach ($mb in 1, 5) {
        try {
            $datos = New-Object byte[] ($mb * 1MB)
            $contenido = [System.Net.Http.ByteArrayContent]::new($datos)
            $sw = [Diagnostics.Stopwatch]::StartNew()
            $resp = $cliente.PostAsync("https://speed.cloudflare.com/__up", $contenido).GetAwaiter().GetResult()
            $seg = $sw.Elapsed.TotalSeconds
            $ok = $resp.IsSuccessStatusCode
            $resp.Dispose(); $contenido.Dispose()
            if (-not $ok) { $res.error = "HTTP error"; break }
            $res.mbps = ($mb * 1MB * 8 / 1e6) / $seg
            if ($seg -gt 2) { break }
        } catch {
            $res.error = ($_.Exception.GetBaseException().Message -replace '[\r\n,;]', ' ')
            break
        }
    }
    return $res
}

$webs = [ordered]@{
    prado     = "https://prado.ugr.es/"
    ugr       = "https://www.ugr.es/"
    github    = "https://github.com/"
    pypi      = "https://pypi.org/"
    google    = "https://www.google.com/"
    wikipedia = "https://es.wikipedia.org/"
}

function Medir-Webs($cliente) {
    $res = [ordered]@{}
    foreach ($k in $webs.Keys) {
        $sw = [Diagnostics.Stopwatch]::StartNew()
        try {
            $resp = $cliente.GetAsync($webs[$k]).GetAwaiter().GetResult()
            [void]$resp.Content.ReadAsByteArrayAsync().GetAwaiter().GetResult()
            $resp.Dispose()
            $res[$k] = $sw.Elapsed.TotalSeconds
        } catch {
            $res[$k] = $null
        }
    }
    return $res
}

function Datos-Wifi {
    $w = [ordered]@{ ssid = ""; bssid = ""; senal = $null; banda = ""; canal = ""; radio = ""; rx = $null; tx = $null; nota = "" }
    try {
        $salida = netsh wlan show interfaces 2>&1 | Out-String
        foreach ($linea in ($salida -split "`r?`n")) {
            if ($linea -match '^\s*SSID\s*:\s*(.+)$') { $w.ssid = $Matches[1].Trim() }
            elseif ($linea -match 'BSSID\s*:\s*([0-9a-fA-F]{2}(:[0-9a-fA-F]{2}){5})') { $w.bssid = $Matches[1] }
            if ($linea -match ':\s*(\d+)\s*%\s*$') { $w.senal = [int]$Matches[1] }
            if ($linea -match '(\d+(?:[.,]\d+)?)\s*GHz') { $w.banda = $Matches[1] -replace ',', '.' }
            if ($linea -match '^\s*(Canal|Channel)\s*:\s*(\d+)') { $w.canal = $Matches[2] }
            if ($linea -match '(802\.11\w+)') { $w.radio = $Matches[1] }
            if ($linea -match '\(Mbps\)\s*:\s*([\d.,]+)') {
                $v = [double]::Parse(($Matches[1] -replace ',', '.'), $inv)
                if ($null -eq $w.rx) { $w.rx = $v } else { $w.tx = $v }
            }
        }
        if (-not $w.ssid) { $w.nota = (($salida.Trim() -split "`r?`n")[0] -replace '[,;]', ' ') }
    } catch { $w.nota = "netsh no disponible" }
    return $w
}

function Medir-Ronda {
    $ahora = Get-Date
    $fila = [ordered]@{}
    $fila.fecha_hora = $ahora.ToString("yyyy-MM-dd HH:mm:ss")
    $fila.lugar = $Lugar

    # Interfaz y router
    $ruta = Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue |
        Sort-Object { $_.RouteMetric + $_.InterfaceMetric } | Select-Object -First 1
    $gw = ""; $dnsServ = ""; $tipo = "sin_conexion"; $interfaz = ""
    if ($ruta) {
        $gw = $ruta.NextHop
        $interfaz = $ruta.InterfaceAlias
        $ad = Get-NetAdapter -InterfaceIndex $ruta.ifIndex -ErrorAction SilentlyContinue
        if ($ad -and ($ad.PhysicalMediaType -match '802\.11|Wireless' -or $ad.InterfaceDescription -match 'Wi-?Fi|Wireless')) { $tipo = "wifi" }
        else { $tipo = "cable_u_otro" }
        $dnsServ = (Get-DnsClientServerAddress -InterfaceIndex $ruta.ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue).ServerAddresses | Select-Object -First 1
    }
    $fila.conexion = $tipo
    $fila.interfaz = $interfaz

    $w = Datos-Wifi
    $fila.wifi_red = $w.ssid
    $fila.wifi_bssid = $w.bssid
    $fila.wifi_senal_pct = $w.senal
    $fila.wifi_banda_ghz = $w.banda
    $fila.wifi_canal = $w.canal
    $fila.wifi_estandar = $w.radio
    $fila.wifi_enlace_rx_mbps = F $w.rx 0
    $fila.wifi_enlace_tx_mbps = F $w.tx 0
    $fila.wifi_nota = $w.nota

    Write-Host "  - ping al router e internet..." -ForegroundColor DarkGray
    $pg = Medir-Ping $gw 20
    $p1 = Medir-Ping "1.1.1.1" 20
    $p2 = Medir-Ping "8.8.8.8" 10
    $fila.router_ip = $gw
    if ($pg.perdida -eq 100 -and $p1.perdida -lt 100) {
        # Muchos routers no contestan al ping: no lo contamos como perdida.
        $fila.router_ping_ms = ""; $fila.router_jitter_ms = ""; $fila.router_perdida_pct = ""
    } else {
        $fila.router_ping_ms = F $pg.media 1; $fila.router_jitter_ms = F $pg.jitter 1; $fila.router_perdida_pct = F $pg.perdida 1
    }
    $fila.inet_ping_ms = F $p1.media 1
    $fila.inet_jitter_ms = F $p1.jitter 1
    $fila.inet_ping_max_ms = F $p1.max 0
    $fila.inet_perdida_pct = F $p1.perdida 1
    $fila.google_ping_ms = F $p2.media 1
    $fila.google_perdida_pct = F $p2.perdida 1

    # DNS
    $dnsT = New-Object System.Collections.Generic.List[double]; $dnsFallos = 0
    foreach ($n in "github.com", "pypi.org", "ugr.es", "google.com") {
        try {
            $ms = (Measure-Command {
                if ($dnsServ) { Resolve-DnsName -Name $n -Server $dnsServ -DnsOnly -QuickTimeout -ErrorAction Stop | Out-Null }
                else { Resolve-DnsName -Name $n -DnsOnly -QuickTimeout -ErrorAction Stop | Out-Null }
            }).TotalMilliseconds
            $dnsT.Add($ms)
        } catch { $dnsFallos++ }
    }
    $fila.dns_ms = if ($dnsT.Count) { F (($dnsT | Measure-Object -Average).Average) 0 } else { "" }
    $fila.dns_fallos = $dnsFallos

    $cliente = Nuevo-Cliente
    try {
        Write-Host "  - velocidad de bajada (2 servidores)..." -ForegroundColor DarkGray
        $bytes = $MaxMBDescarga * 1000000
        $d1 = Medir-Descarga $cliente "https://speed.cloudflare.com/__down?bytes=$bytes"
        $d2 = Medir-Descarga $cliente "https://proof.ovh.net/files/100Mb.dat"
        Write-Host "  - velocidad de subida..." -ForegroundColor DarkGray
        $u = Medir-Subida $cliente
        Write-Host "  - tiempo de respuesta de webs..." -ForegroundColor DarkGray
        $wb = Medir-Webs $cliente
    } finally { $cliente.Dispose() }

    $fila.bajada_cloudflare_mbps = F $d1.mbps 2
    $fila.bajada_ovh_mbps = F $d2.mbps 2
    $fila.subida_mbps = F $u.mbps 2
    $fila.error_bajada = (@($d1.error, $d2.error) | Where-Object { $_ }) -join " | "
    $fila.error_subida = $u.error
    $tiempos = @()
    $fallosWeb = 0
    foreach ($k in $webs.Keys) {
        $fila["web_${k}_s"] = F $wb[$k] 2
        if ($null -eq $wb[$k]) { $fallosWeb++ } else { $tiempos += $wb[$k] }
    }
    $fila.web_media_s = if ($tiempos.Count) { F (($tiempos | Measure-Object -Average).Average) 2 } else { "" }
    $fila.web_fallos = $fallosWeb

    $sinRed = ($p1.perdida -eq 100) -and ($null -eq $d1.mbps) -and ($null -eq $d2.mbps)
    $fila.hay_conexion = if ($sinRed) { 0 } else { 1 }

    [pscustomobject]$fila | Export-Csv -Path $Salida -Append -NoTypeInformation -Encoding UTF8

    # Resumen en pantalla
    $b = @($d1.mbps, $d2.mbps) | Where-Object { $null -ne $_ } | Measure-Object -Maximum
    $bTxt = if ($b.Count) { "{0:N1} Mbps" -f $b.Maximum } else { "FALLO" }
    $uTxt = if ($null -ne $u.mbps) { "{0:N1} Mbps" -f $u.mbps } else { "FALLO" }
    $pTxt = if ($null -ne $p1.media) { "{0:N0} ms" -f $p1.media } else { "sin respuesta" }
    $wTxt = if ($tiempos.Count) { "{0:N1} s" -f (($tiempos | Measure-Object -Average).Average) } else { "FALLO" }
    $sTxt = if ($null -ne $w.senal) { "$($w.senal)%" } else { "?" }
    Write-Host ("[{0}] Bajada {1} | Subida {2} | Ping {3} | Perdida {4:N0}% | Webs {5} | Senal wifi {6}" -f `
        $ahora.ToString("dd/MM HH:mm"), $bTxt, $uTxt, $pTxt, $p1.perdida, $wTxt, $sTxt) -ForegroundColor Cyan
}

Write-Host ""
Write-Host "=== Medidor de conexion ===" -ForegroundColor Green
Write-Host "Lugar: $Lugar"
Write-Host "Datos: $Salida"
if (-not $UnaVez) {
    Write-Host "Medira cada $IntervaloMin minutos. Deja esta ventana abierta y el portatil enchufado y con la tapa abierta."
    Write-Host "Para parar: cierra la ventana o pulsa Ctrl+C."
}
Write-Host ""

$ronda = 0
while ($true) {
    $ronda++
    $inicio = Get-Date
    Write-Host ("Medicion {0} ({1})..." -f $ronda, $inicio.ToString("HH:mm:ss"))
    try { Medir-Ronda } catch { Write-Host "Error en la medicion: $($_.Exception.Message)" -ForegroundColor Red }
    if ($UnaVez) { break }
    $siguiente = $inicio.AddMinutes($IntervaloMin)
    $espera = ($siguiente - (Get-Date)).TotalSeconds
    Write-Host ("Siguiente medicion a las {0}" -f $siguiente.ToString("HH:mm")) -ForegroundColor DarkGray
    if ($espera -gt 0) { Start-Sleep -Seconds ([int]$espera) }
}
Write-Host ""
Write-Host "Listo. Datos guardados en $Salida" -ForegroundColor Green
