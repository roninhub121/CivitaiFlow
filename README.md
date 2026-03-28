# 📡 CivitaiFlow v21 (Resilience Edition)

> **The definitive "Set & Forget" workflow for LoRA hunters on Stable Diffusion Forge.**

CivitaiFlow es una extensión nativa para **Stable Diffusion WebUI Forge** diseñada para optimizar radicalmente la ingesta masiva de modelos desde Civitai. Olvídate de descargar manualmente, organizar archivos en carpetas, o lidiar con crasheos de memoria. Esta herramienta automatiza todo el proceso: desde que copias un enlace en tu navegador hasta que el LoRA está listo y etiquetado en tu disco duro.

![CivitaiFlow Interface](https://via.placeholder.com/800x400?text=CivitaiFlow+v21+Interface+Preview) 
*(Nota: Añade aquí un GIF o screenshot de la extensión funcionando)*

---

## 🚀 Características Principales

* **🎯 Sniper Mode (Clipboard Monitor):** Escucha silenciosa del portapapeles. Si detecta un link válido de Civitai, la extensión lo captura automáticamente sin necesidad de pegarlo.
* **⚡ Auto-DL (Zero-Click):** Descarga inmediata en segundo plano. No hay botones de "Procesar"; si lo copias, se descarga.
* **🛡️ Segfault-Proof Architecture:** Implementación de lectura de memoria mediante subprocesos aislados del OS. Elimina los crasheos por violaciones de acceso a la memoria (`Access Violation`) comunes en extensiones multihilo.
* **🔄 Resilience Engine:** Manejo inteligente de caídas de API (HTTP 429, 503). Botón de reintento masivo para descargas fallidas por saturación del servidor.
* **🧹 Smart UI Purge:** Monitor de tráfico inteligente. Los éxitos se limpian de la pantalla tras **8 segundos**, mientras que los errores persisten **60 segundos** para tu supervisión.
* **📂 Auto-Organization:** Crea carpetas dinámicas basadas en las etiquetas oficiales de Civitai (e.g., `Lora/Character`, `Lora/Style`).
* **📝 Forge Integration:** Genera archivos `.json` e `.info` compatibles con Forge para mostrar metadatos, imágenes de vista previa y palabras de activación (Trigger Words) automáticamente.

---

## 🧠 Technical Deep Dive (Arquitectura)

Para los usuarios avanzados y desarrolladores, CivitaiFlow resuelve dos de los problemas más grandes al crear extensiones en Gradio/FastAPI:

1. **El problema del Portapapeles (Memory Crashes):** Las llamadas directas a la API de Windows mediante `ctypes` desde hilos asíncronos en Python suelen chocar con los bloqueos de memoria del SO, provocando el cierre abrupto de `python.exe`. CivitaiFlow lo soluciona utilizando un **PowerShell Bridge** (`subprocess.check_output`), aislando la lectura de memoria en un proceso independiente del sistema operativo.
2. **Websocket Timeouts:** En lugar de saturar el servidor de Forge con peticiones de frontend constantes, el estado de las descargas se maneja en un diccionario global en backend (`ThreadPoolExecutor`), y la UI simplemente hace un *polling* ligero y pasivo cada 1.5 segundos mediante `gr.Timer`.

---

## 🛠️ Instalación

1. Abre **Stable Diffusion Forge**.
2. Ve a la pestaña **Extensions** -> **Install from URL**.
3. Pega la URL de este repositorio: `https://github.com/roninhub121/CivitaiFlow`
4. Haz clic en **Install**.
5. Ve a la pestaña **Installed**, haz clic en **Apply and restart UI** (o cierra y abre la consola negra).

---

## ⚙️ Configuración Obligatoria (API Key)

Civitai requiere autenticación para descargar modelos, especialmente aquellos marcados como NSFW o de acceso anticipado.

1. Ve a tu cuenta en [Civitai Settings](https://civitai.com/user/settings).
2. Desplázate hacia abajo hasta **API Keys** y haz clic en **Add API Key**.
3. Copia la clave generada.
4. En la interfaz de Forge, ve a la pestaña **Settings** -> **CivitaiFlow Manager**.
5. Pega tu clave en la casilla correspondiente y haz clic en **Apply Settings** en la parte superior.

---

## 📖 Cómo usarlo (Zero-Click Workflow)

La filosofía de CivitaiFlow es que la interfaz solo está para ser observada.

1. Entra a la pestaña **CivitaiFlow**. Verás que **Sniper** y **Auto-DL** están activados por defecto.
2. Navega por Civitai en el navegador de la derecha (o en tu propio navegador web).
3. Haz **clic derecho -> Copiar dirección de enlace** en cualquier modelo o botón de descarga.
4. **No hagas nada más.** El enlace aparecerá un instante en la caja de ingesta y bajará al Monitor de Tráfico, donde la descarga comenzará inmediatamente.

---

## 🚑 Troubleshooting (Solución de problemas)

* **Error: HTTP 429 (Too Many Requests) o 503:** Los servidores de Civitai están saturados. Espera unos minutos y presiona el botón naranja `🔄 REINTENTAR ERRORES`. Recomendación: Baja los "Hilos Simultáneos" en la configuración de Red a 2 o 3.
* **Error de API Key:** Asegúrate de que no haya espacios en blanco al inicio o final de tu API Key en los Settings de Forge.
* **El Sniper no captura los enlaces:** Verifica que tu Windows no tenga políticas de seguridad restrictivas que bloqueen la ejecución de comandos de PowerShell en segundo plano.

---

## 🗺️ Roadmap (Próximamente)

- [ ] Soporte extendido para descarga de Checkpoints, VAEs y Embeddings con auto-enrutamiento.
- [ ] Integración con la API de Tensor.art.
- [ ] Vista previa de galería local para los modelos recién descargados directamente en la pestaña.

---

## 👤 Créditos
Desarrollado y mantenido por **Ronin**.
Diseño de arquitectura con el apoyo de **Gemini AI**.

*In IT we trust.*
