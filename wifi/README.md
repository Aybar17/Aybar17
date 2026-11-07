# Wifi de la residencia: pruebas para la reclamación

Kit para medir la conexión con datos verificables, convertirlos en un informe y presentar una reclamación al gerente que no se pueda despachar con un «a mí me va bien».

| Archivo | Para qué sirve |
|---|---|
| `iniciar-medicion.bat` | Mide cada 15 minutos desde la habitación hasta que cierras la ventana |
| `prueba-rapida.bat` | Hace una sola medición indicando el lugar (junto al router, datos móviles, cable…) |
| `medir-wifi.ps1` | El medidor en sí (PowerShell; no instala nada ni pide permisos de administrador) |
| `analizar.py` | Convierte los CSV en un informe con gráficas, imprimible en PDF |
| `carta-gerente.md` | Plantilla de la reclamación |

Los datos se guardan en `datos/mediciones.csv`, junto a los scripts. Esa carpeta **no se sube al repositorio**, que es público.

---

## Calendario (sábado 7 → lunes 9 de noviembre)

### Sábado por la noche: empezar a medir

1. **Descarga la carpeta** en el portátil, con el ZIP de la rama o los archivos sueltos. Antes de descomprimir el ZIP: clic derecho → *Propiedades* → marca *Desbloquear* → *Aceptar*.
2. **Descarta los fallos de tu lado** (5 minutos). El gerente te lo preguntará:
   - reinicia el portátil;
   - pausa OneDrive, Windows Update, Steam o cualquier descarga, y desactiva la VPN si usas una;
   - en *Configuración → Red e Internet → Wi-Fi → Administrar redes conocidas*, olvida la red de la residencia y vuelve a conectarte;
   - si aparece una variante de la red en 5 GHz, conéctate a esa.
3. **Activa la ubicación** en *Configuración → Privacidad y seguridad → Ubicación*, incluida la opción de dejar que las aplicaciones de escritorio la usen. Windows 11 la exige para dar los datos de señal y punto de acceso. El script funciona sin ella, pero el informe pierde la parte de cobertura.
4. **Deja el portátil enchufado y con la tapa abierta**, o configura *Al cerrar la tapa: no hacer nada* cuando esté enchufado.
5. Doble clic en **`iniciar-medicion.bat`**. Si sale «Windows protegió su PC», pulsa *Más información → Ejecutar de todas formas*. Verás una línea por medición, por ejemplo:
   `[07/11 21:15] Bajada 3,2 Mbps | Subida 0,9 Mbps | Ping 140 ms | Perdida 6% | Webs 4,1 s | Senal wifi 72%`
6. Déjalo funcionando **hasta el lunes por la mañana**. Puedes usar el portátil con normalidad, pero no hagas descargas grandes mientras tanto: falsearían las mediciones.

### Domingo: pruebas de control (para quitarles las excusas)

**Antes de cada control cierra la ventana de la medición continua**. Si no, sus mediciones se guardarían con la etiqueta «habitación». Al terminar, vuelve a abrir `iniciar-medicion.bat`.

| Excusa | Control | Cómo |
|---|---|---|
| «Es tu portátil» | Mismo portátil, otra red | Comparte datos desde el móvil, conecta el portátil a ese punto de acceso y ejecuta `prueba-rapida.bat` con el lugar `datos-moviles`. Hazlo 2 o 3 veces; cada prueba gasta unos 50 MB de datos. |
| «Es que tu habitación está lejos» | Misma red, junto al router | Ve a la zona común con el portátil y ejecuta `prueba-rapida.bat` con el lugar `junto-al-router` 2 o 3 veces. |
| «Es el wifi, la línea va bien» | Por cable | Solo si hay una toma de red: `prueba-rapida.bat` con el lugar `cable`. |
| «El speedtest no es fiable» | Otras herramientas | Capturas de pantalla con la hora visible de [speedtest.net](https://www.speedtest.net), [fast.com](https://fast.com) y [speed.cloudflare.com](https://speed.cloudflare.com), sobre todo entre las 20 y las 23 h. |

Guarda también:
- capturas de **descargas reales** lentas: el navegador mostrando la velocidad, o `pip install` y `conda` tardando;
- una captura de la **web o el contrato** de la residencia donde se anuncie el wifi o internet («wifi de alta velocidad», «internet incluido»…), con fecha y dirección de la página.

### Domingo por la noche o lunes temprano: informe

Cierra la medición y adjunta `datos\mediciones.csv` en esta conversación. Con él genero:
- el **informe en PDF**, con gráficas, la lectura de los datos y una tabla de tiempos de descarga reales;
- la **carta rellenada** con tus cifras, sin redondear nada a tu favor.

Si prefieres hacerlo tú, con Python, pandas y matplotlib:
```
python analizar.py datos/mediciones.csv --salida informe.html --habitacion 214
```
Luego abre `informe.html` en el navegador e imprímelo en PDF. Si sabes la velocidad que anuncia la residencia, añade `--contratado 300`.

### Lunes: la reunión

1. Lleva el **informe impreso** y la **carta por duplicado**. Pide que te firmen o sellen tu copia con la fecha.
2. Si te dicen que ahora va bien, ejecuta `prueba-rapida.bat` delante del gerente, pero no dependas de eso: el valor está en las 48 horas de datos.
3. Pide **compromisos concretos**: quién lo revisa, qué se va a hacer y para qué fecha. Que te contesten **por escrito**, aunque sea por correo.
4. Ofrece repetir las mediciones después de cada cambio, para comprobar entre ambos si se ha resuelto.

### Si no responden en el plazo

- **Residencia privada:** en Andalucía, toda empresa que presta servicios debe tener **hojas de quejas y reclamaciones** a disposición de los usuarios (Decreto 82/2022 de la Junta de Andalucía). Si no recibes respuesta o no estás de acuerdo con ella, puedes llevar tu ejemplar a la **OMIC** (Oficina Municipal de Información al Consumidor) de tu municipio.
- **Residencia o colegio mayor de la UGR:** la vía puede ser otra, por ejemplo la Defensoría Universitaria. Compruébalo antes de dar ese paso.
- En ambos casos, guarda el informe, la carta sellada y las respuestas que recibas.

---

## Qué mide el script y por qué

| Medida | Qué demuestra |
|---|---|
| Bajada contra **dos servidores independientes** (Cloudflare y OVH), tomando el mejor | Que no es culpa de un servidor concreto; el método es conservador y favorece a la residencia |
| Subida | Videollamadas, subir entregas o hacer `git push` |
| Ping, jitter y pérdida **a internet** | Por qué las webs «se quedan pensando» aunque la velocidad parezca aceptable |
| Ping y pérdida **al router o punto de acceso** | Si falla el enlace wifi de la habitación o lo que hay más allá (línea saturada) |
| Señal %, banda, canal y punto de acceso (BSSID) | Si es un problema de cobertura o de capacidad |
| Respuesta de PRADO, UGR, GitHub, PyPI, Google y Wikipedia | El impacto en las webs que usas para la carrera |
| Hora de cada medición | Si empeora en horas punta, lo típico de una red saturada |

Cada prueba de bajada dura como máximo 12 segundos o 20 MB, así que el script ocupa la red alrededor de un 2-3 % del tiempo. No se le puede acusar de ser él quien satura la red.

## Referencias usadas en el informe

- **Ley 11/2022 General de Telecomunicaciones, art. 37:** el servicio universal garantiza acceso a internet de banda ancha desde una ubicación fija a un mínimo de **10 Mbit/s de bajada** ([Ministerio para la Transformación Digital](https://digital.gob.es/telecomunicaciones-infraestructuras-digitales/servicios/servicio-universal)). Hay un proyecto de reglamento de 2026 que propone subirlo a 100 Mbit/s. Como todavía no está aprobado, el informe no lo usa como referencia.
- **Zoom:** para una videollamada de grupo en 1080p recomienda 3,8 Mbps de bajada y 3,0 de subida ([support.zoom.com, KB0060748](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0060748)).
- **PyTorch:** el paquete pip para Windows sin GPU pesa unos 124 MB ([PyPI](https://pypi.org/project/torch)); el paquete conda con CUDA para Windows, entre 1,2 y 1,4 GB ([anaconda.org](https://anaconda.org/pytorch/pytorch/files)).
- **Hojas de quejas y reclamaciones en Andalucía:** Decreto 82/2022, de 17 de mayo ([BOJA](https://www.juntadeandalucia.es/boja/2022/95/42.html)).

## Límites

- Las mediciones describen la conexión **desde tu portátil y tu habitación**, no la de toda la residencia. Si otros residentes tienen el mismo problema, que midan también: varias habitaciones pesan mucho más.
- El tiempo de respuesta de las webs mide solo el documento principal. Una carga completa en el navegador tarda más.
- El medidor se ha probado aquí con PowerShell 7 en Linux, simulando las órdenes de Windows (`netsh`, `Get-NetRoute`). La primera ejecución real en tu Windows es la prueba definitiva: si algo falla, pásame lo que salga en la ventana.
