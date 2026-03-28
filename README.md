# 📡 CivitaiFlow v21 (Resilience Edition)
> **The definitive "Set & Forget" workflow for LoRA hunters on Stable Diffusion Forge.**

CivitaiFlow es una extensión diseñada para optimizar radicalmente la ingesta de modelos desde Civitai. Olvídate de descargar manualmente, mover archivos de carpetas o lidiar con crasheos de memoria. Esta herramienta automatiza el proceso desde que haces "clic derecho -> copiar" en tu navegador hasta que el LoRA está listo en tu carpeta de modelos.

![CivitaiFlow Interface](https://via.placeholder.com/800x400?text=CivitaiFlow+v21+Interface+Preview) ---

## 🚀 Características Principales

* **🎯 Sniper Mode (Clipboard Monitor):** Escucha el portapapeles de Windows de forma aislada. Si copias un link de Civitai, la extensión lo captura al instante.
* **⚡ Auto-DL (Zero-Click):** Descarga automática inmediata tras la captura o el pegado manual. 
* **🛡️ Segfault-Proof Architecture:** Implementación de lectura de memoria mediante subprocesos aislados del OS (PowerShell Bridge), eliminando los crasheos de memoria (`Access Violation`) comunes en integraciones directas.
* **🔄 Resilience Engine:** Manejo inteligente de errores (HTTP 429, 503). Botón de reintento masivo para descargas fallidas por saturación de la API.
* **🧹 Smart UI Purge:** * Los éxitos se limpian del monitor tras **8 segundos**.
    * Los errores persisten **60 segundos** para supervisión.
    * Puente de ingesta minimalista que se purga tras cada detección.
* **📂 Auto-Organization:** Crea carpetas automáticamente basadas en los tags de Civitai (e.g., `Lora/Character`, `Lora/Style`).
* **📝 Forge Integration:** Genera archivos `.json` compatibles con Forge para mostrar metadatos y palabras de activación automáticamente.

---

## 🛠️ Instalación

1. Abre **Stable Diffusion Forge**.
2. Ve a la pestaña **Extensions** -> **Install from URL**.
3. Pega la URL de este repositorio: `[TU_URL_DE_GITHUB]`
4. Haz clic en **Install**.
5. Reinicia la UI de Forge (o cierra y abre la consola negra).

---

## ⚙️ Configuración Obligatoria

Para que las descargas funcionen, necesitas tu API Key de Civitai:
1. Ve a [Civitai Settings](https://civitai.com/user/settings).
2. Genera un **API Key**.
3. En Forge, ve a **Settings** -> **CivitaiFlow Manager**.
4. Pega tu clave y dale a **Apply Settings**.

---

## 📖 Cómo usarlo

1. Entra a la pestaña **CivitaiFlow**.
2. Asegúrate de que **🎯 Sniper** y **⚡ Auto-DL** estén encendidos (vienen ON por defecto).
3. Navega en el panel derecho de Civitai.
4. Cuando veas un LoRA que te guste, dale **Clic derecho -> Copiar dirección de enlace** a la miniatura o al botón de descarga.
5. **¡Listo!** Mira el monitor de tráfico; la descarga comenzará sola.

---

## 🛠️ Stack Tecnológico

* **Backend:** Python 3.10+
* **UI:** Gradio 4.40+ (Nativo Forge)
* **Bridge:** Windows PowerShell Subprocess
* **Networking:** Requests (Streaming enabled)

---

## 👤 Créditos
Desarrollado por **Ronin** con el apoyo de **Gemini AI**. 
*In IT we trust.*
