import os
import requests
import json
import re
import modules.scripts as scripts
import gradio as gr
from modules import paths, shared, script_callbacks
from concurrent.futures import ThreadPoolExecutor

LORA_DIR = os.path.join(paths.models_path, "Lora")

def on_ui_settings():
    section = ('civitai_flow', "CivitaiFlow Manager")
    shared.opts.add_option("civitai_api_key", shared.OptionInfo("", "Civitai API Key (Ronin Edition)", gr.Textbox, {"visible": True}, section=section))
script_callbacks.on_ui_settings(on_ui_settings)

def parse_civitai_urls(text):
    ids = []
    for line in text.split('\n'):
        line = line.strip()
        if not line: continue
        match = re.search(r'models/(\d+)', line)
        if match: ids.append(match.group(1))
        elif line.isdigit(): ids.append(line)
    return list(set(ids))

def download_by_id(model_id, api_key):
    headers = {"Authorization": f"Bearer {api_key}", "User-Agent": "Mozilla/5.0"}
    try:
        model_url = f"https://civitai.com/api/v1/models/{model_id}"
        model_data = requests.get(model_url, headers=headers, timeout=10).json()
        if 'modelVersions' not in model_data: return f"[ERR] No se encontró el modelo {model_id}"
        version = model_data['modelVersions'][0] 
    except Exception as e:
        return f"[CRIT] Falla al conectar con API para ID {model_id}: {str(e)}"

    clean_name = "".join([c for c in model_data['name'] if c.isalnum() or c in (' ', '_')]).rstrip()
    category = model_data['tags'][0].replace(' ', '_').replace('/', '_') if model_data.get('tags') else "General"
    
    target_dir = os.path.join(LORA_DIR, category)
    os.makedirs(target_dir, exist_ok=True)
    
    base_path = os.path.join(target_dir, clean_name)
    safetensors_path = f"{base_path}.safetensors"
    info_path = f"{base_path}.civitai.info" 
    preview_path = f"{base_path}.preview.png"

    if os.path.exists(safetensors_path): return f"[SKIP] {clean_name} (Ya existe)"

    log = []
    try:
        v_url = f"https://civitai.com/api/v1/model-versions/{version['id']}"
        v_info = requests.get(v_url, headers=headers, timeout=10).json()
        with open(info_path, 'w', encoding='utf-8') as f: json.dump(v_info, f, indent=4)
        
        if version.get('images'):
            img_r = requests.get(version['images'][0]['url'], timeout=10)
            with open(preview_path, 'wb') as f: f.write(img_r.content)

        dl_url = f"https://civitai.com/api/download/models/{version['id']}"
        r = requests.get(dl_url + f"?token={api_key}", stream=True, timeout=600)
        
        if r.status_code == 200:
            with open(safetensors_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk: f.write(chunk)
            log.append(f"[OK] {clean_name}")
        else: log.append(f"[ERR] {clean_name} (HTTP {r.status_code})")
    except Exception as e: log.append(f"[CRIT] Error en {clean_name}: {str(e)}")
        
    return "\n".join(log)

def process_bulk_download(text_input, threads):
    api_key = shared.opts.data.get("civitai_api_key", "")
    if not api_key: return "❌ Configura tu API Key en la pestaña Settings."
    
    ids_to_download = parse_civitai_urls(text_input)
    if not ids_to_download: return "⚠️ No se detectaron Links válidos de Civitai."

    final_log = [f"🚀 Iniciando descarga de {len(ids_to_download)} modelos por URL..."]
    with ThreadPoolExecutor(max_workers=int(threads)) as executor:
        futures = [executor.submit(download_by_id, m_id, api_key) for m_id in ids_to_download]
        for future in futures: final_log.append(future.result())
    return "\n".join(final_log)

def on_ui_tabs():
    with gr.Blocks(analytics_enabled=False) as civitai_flow_tab:
        gr.Markdown("## 📡 CivitaiFlow: Hybrid Web-Downloader v6.2")
        
        # El Slider inyector de JS (Va fuera de las columnas para controlar todo)
        ui_scale = gr.Slider(minimum=1, maximum=9, step=1, value=3, label="↔️ Redimensionar Interfaz (Izquierda : Derecha)")
        
        with gr.Row(elem_id="cf_main_row"):
            # Panel Izquierdo
            with gr.Column(scale=3, elem_id="cf_left_panel"):
                gr.Markdown("### 1. Panel de Ingesta (Pega los Links aquí)")
                url_input = gr.Textbox(label="URLs de Civitai (Usa Win + V)", placeholder="Clic derecho -> Copiar enlace...", lines=10)
                
                with gr.Row():
                    clear_btn = gr.Button("🗑️ Limpiar Caja", variant="secondary")
                    threads_slider = gr.Slider(minimum=1, maximum=10, step=1, label="Hilos Paralelos", value=5)
                
                download_btn = gr.Button("⬇️ Descargar Enlaces", variant="primary", size="lg")
                status_log = gr.Textbox(label="Consola de Descarga", lines=6)

            # Panel Derecho
            with gr.Column(scale=7, elem_id="cf_right_panel"):
                gr.HTML('<iframe src="https://civitai.com" style="width: 100%; height: 82vh; border: 2px solid #333; border-radius: 8px;"></iframe>')

        # --- LA MAGIA DE JAVASCRIPT ---
        js_resize = """
        (val) => {
            let left = document.getElementById('cf_left_panel');
            let right = document.getElementById('cf_right_panel');
            if (left && right) {
                left.style.flexGrow = val;
                left.style.width = (val * 10) + '%';
                right.style.flexGrow = 10 - val;
                right.style.width = ((10 - val) * 10) + '%';
            }
        }
        """
        ui_scale.change(fn=None, inputs=[ui_scale], js=js_resize)

        # Eventos normales
        download_btn.click(fn=process_bulk_download, inputs=[url_input, threads_slider], outputs=status_log)
        clear_btn.click(fn=lambda: "", inputs=[], outputs=url_input)
        
    return [(civitai_flow_tab, "CivitaiFlow", "civitai_flow_tab")]

script_callbacks.on_ui_tabs(on_ui_tabs)
