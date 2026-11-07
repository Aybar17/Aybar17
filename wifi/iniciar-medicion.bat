@echo off
title Medidor de conexion - deja esta ventana abierta
echo Iniciando medicion continua (cada 15 minutos) desde la habitacion...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0medir-wifi.ps1" -Lugar habitacion -IntervaloMin 15
pause
