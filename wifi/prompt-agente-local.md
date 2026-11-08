Trabajas en mi portátil Windows, conectado al wifi de mi residencia de estudiantes. Soy José Luis (Aybar). El lunes 9 de noviembre de 2026 por la mañana voy a reclamar al gerente de la residencia porque el wifi va muy mal: las descargas tardan muchísimo y los navegadores también. Necesito pruebas objetivas, con fecha y hora, para que no me digan que «va bien». Mientras duermo, quiero que dejes las mediciones funcionando y que el lunes temprano generes el informe y la carta.

## Material ya preparado
En la rama `claude/wifi-issues-documentation-ydok2a` del repositorio público `Aybar17/Aybar17`, carpeta `wifi/`:
- `medir-wifi.ps1`: medidor en PowerShell, sin dependencias ni permisos de administrador. Cada ronda guarda una fila en `datos\mediciones.csv` con bajada (Cloudflare y OVH), subida, ping, jitter y pérdida hacia internet y hacia el router, DNS, señal, banda, canal y BSSID del wifi (vía `netsh`), y el tiempo de respuesta de PRADO, UGR, GitHub, PyPI, Google y Wikipedia. Parámetros: `-Lugar`, `-IntervaloMin` (15 por defecto), `-UnaVez`.
- `iniciar-medicion.bat`: bucle cada 15 minutos con el lugar `habitacion`; impide la suspensión mientras está abierto.
- `prueba-rapida.bat`: una sola medición; pregunta el lugar.
- `analizar.py`: genera un informe HTML imprimible a partir de los CSV. Necesita pandas y matplotlib. Uso: `python analizar.py datos\mediciones.csv --salida informe.html [--habitacion N] [--contratado MBPS]`.
- `carta-gerente.md`: plantilla de la reclamación, con huecos `[...]`.
- `README.md`: guía completa.

Descarga directa, sustituyendo ARCHIVO:
`https://raw.githubusercontent.com/Aybar17/Aybar17/claude/wifi-issues-documentation-ydok2a/wifi/ARCHIVO`

## Lo que tienes que hacer

### 1. Preparar (ahora)
1. Crea la carpeta `%USERPROFILE%\Documents\wifi-residencia` (si ya existe, no borres nada) y descarga ahí los 6 archivos.
2. **Lee `medir-wifi.ps1` antes de ejecutarlo** y confirma que solo hace mediciones: ping, descargas de prueba limitadas a unos 20 MB y 12 s, una subida de prueba, peticiones a webs públicas y `netsh wlan show interfaces`. Si encuentras algo distinto, no lo ejecutes y déjamelo anotado.
3. Comprueba y anota (sin cambiar nada todavía):
   - si el portátil está conectado por wifi y a qué red y banda: `netsh wlan show interfaces`;
   - si hay una VPN activa;
   - si hay descargas grandes en segundo plano: OneDrive, Windows Update, Steam, torrents. Puedes pausar OneDrive o las descargas durante la medición, pero apunta qué has pausado para reanudarlo al final.
   - si `netsh` pide permiso de ubicación. Si lo pide, déjamelo anotado: lo activo yo al despertar, no lo cambies tú.

### 2. Dejar la medición en marcha
1. Lanza `iniciar-medicion.bat` como proceso independiente, en su propia ventana, para que siga aunque termine tu sesión: `Start-Process -FilePath "<carpeta>\iniciar-medicion.bat" -WorkingDirectory "<carpeta>"`.
2. Espera a que termine la primera ronda (1-2 minutos) y comprueba que en `datos\mediciones.csv` hay una fila con valores razonables. Si algo falla (error de PowerShell, columnas vacías, `netsh` sin datos), diagnostícalo y corrígelo. Las correcciones deben ser mínimas, quedar documentadas y conservar el original como `medir-wifi.original.ps1`.
3. **Suspensión:** el script impide la suspensión por inactividad, pero no la del cierre de la tapa. Te autorizo a una sola cosa: si al cerrar la tapa con el portátil enchufado se suspende, cambia esa acción a «no hacer nada». Hazlo solo con el portátil enchufado, apunta el valor anterior y restáuralo en el paso 4. No toques ningún otro ajuste de energía.
4. No hagas descargas grandes ni pruebas adicionales mientras mide: contaminarían los datos.

### 3. Controles que necesitan que yo esté despierto (déjamelos preparados, no los hagas tú)
Escribe una nota corta `PENDIENTE-para-Aybar.txt` en la carpeta con estos pasos. Antes de cada control hay que cerrar la ventana de medición y, después, volver a abrir `iniciar-medicion.bat`.
- Compartir datos desde el móvil, conectar el portátil a esa red y ejecutar `prueba-rapida.bat` con el lugar `datos-moviles`, 2 o 3 veces (unos 50 MB cada una). Sirve para demostrar que el portátil no es el problema.
- Llevar el portátil a la zona común o junto al router y ejecutar `prueba-rapida.bat` con el lugar `junto-al-router`, 2 o 3 veces.
- Si hay toma de red en la habitación: `prueba-rapida.bat` con el lugar `cable`.
- Activar la ubicación de Windows si `netsh` la pidió.
- Hacer capturas de speedtest.net o fast.com entre las 20 y las 23 h, y de la web o el contrato de la residencia donde se anuncie el wifi.

### 4. El lunes por la mañana, antes de las 8:00 (o cuando te lo pida)
Si puedes programar una tarea que te despierte el lunes a las 7:00, hazlo. Si no, para aquí y retómalo cuando te escriba «continúa con el paso 4».
1. Cierra la ventana de medición, restaura la acción de la tapa y reanuda lo que hubieras pausado.
2. Crea un entorno virtual en la carpeta, instala pandas y matplotlib y ejecuta:
   `python analizar.py datos\mediciones.csv --salida informe-wifi.html`
   Añade `--habitacion` y `--contratado` solo si los he dejado indicados. **No inventes una velocidad contratada.**
3. Convierte el informe a PDF, por ejemplo con Edge en modo headless: `msedge --headless --print-to-pdf="<carpeta>\informe-wifi.pdf" "<carpeta>\informe-wifi.html"`. Abre el PDF y comprueba que se leen las gráficas y las tablas.
4. Rellena la carta a partir de `carta-gerente.md` y guárdala como `carta-gerente-rellenada.md` y, si puedes, también en PDF o Word para imprimir:
   - usa **exactamente** las cifras del informe, sin redondear a mi favor;
   - incluye solo los párrafos marcados «Si se cumple» que los datos respalden de verdad;
   - deja en blanco lo que no sepas (nombre del gerente, número de habitación, mi contacto) y márcalo para que lo complete yo;
   - no incluyas el párrafo opcional del final, el de las «vías formales»: esa decisión es mía.
5. Si hay menos de unas 30 mediciones, o los datos no muestran un problema claro, dilo tal cual. No fuerces la conclusión.

## Límites
- **No envíes, publiques ni subas nada:** ni correos, ni mensajes al gerente, ni commits. Mis mediciones e informes no van al repositorio, que es público. Todo se queda en la carpeta local.
- **Solo mediciones desde este portátil:** no hagas escaneos de la red de la residencia, no intentes acceder al router o a otros dispositivos y no hagas pruebas que saturen la red.
- **Ajustes del sistema:** no cambies ninguno aparte de la acción de la tapa autorizada arriba.
- **Lo que no puedas hacer:** si algo requiere mi presencia o una decisión mía, apúntalo en `PENDIENTE-para-Aybar.txt` y sigue con lo demás.

## Al terminar
Escríbeme un resumen breve en español:
- qué has hecho;
- cuántas mediciones hay y entre qué horas;
- las cifras clave: bajada mediana y del peor 10 %, % de mediciones bajo 10 Mbps, cortes, ping y pérdida;
- cómo lo has comprobado;
- qué ajustes cambiaste y si están restaurados;
- qué queda pendiente para mí antes de la reunión.
