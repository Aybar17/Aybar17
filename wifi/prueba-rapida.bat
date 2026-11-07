@echo off
title Prueba rapida de conexion
echo Escribe donde estas midiendo, sin espacios. Ejemplos:
echo   habitacion   junto-al-router   sala-comun   datos-moviles   cable
set /p LUGAR=Lugar:
if "%LUGAR%"=="" set LUGAR=sin-indicar
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0medir-wifi.ps1" -UnaVez -Lugar "%LUGAR%"
pause
