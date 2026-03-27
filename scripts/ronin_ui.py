import os
import requests
import json
import re
import time
import threading
import modules.scripts as scripts
import gradio as gr
from modules import paths, shared, script_callbacks
from concurrent.futures import ThreadPoolExecutor

LORA_DIR = os.path.join(paths.models_path, "Lora")

# Variables Globales para persistencia de sesión
download_status = {}
active_tasks = 0
task_lock = threading.Lock()

def on_ui_settings():
    section = ('civitai_flow', "CivitaiFlow Manager")
    shared.opts.add_option("civitai_api_key", shared.OptionInfo("", "Civitai API Key (Ronin Edition)", gr.Textbox, {"visible": True}, section=section))
script_callbacks.on_ui_settings(on_ui_settings)

def parse_civitai_urls(text):
    matches = re.findall(r'models/(\d+)', text)
    numbers = re.findall(r'^\d+$', text, re.MULTILINE)
    return list(set(matches + numbers))

def download_by_id(model_id, api_key):
    global download_status
    tracker_name = f"ID: {model_id}"
    
    if tracker_name in download_status and "⬇️" in download_status[tracker_name]:
        return

    download_status[tracker_name] = "🔄 Obteniendo metadata..."
    headers = {"Authorization": f"Bearer {api_key}", "User-Agent": "Mozilla/5.0"}
    
    try:
        model_url = f"https://civitai.com/api/v1/models/{model_id}"
        model_data = requests.get(model_url, headers=headers, timeout=15).json()
        if 'modelVersions' not in model_data: 
            download_status[tracker_name] = "❌ Error: Modelo no encontrado"
            return
        version = model_data['modelVersions'][0] 
    except Exception as e:
        download_status[tracker_name] = f"❌ Error API: {str(e)}"
        return

    clean_name = "".join([c for c in model_data['name'] if c.isalnum() or c in (' ', '_')]).rstrip()
    category = model_data['tags'][0].replace(' ', '_').replace('/', '_') if model_data.get('tags') else "General"
    
    if tracker_name in download_status:
        del download_status[tracker_name]
    tracker_name = clean_name
    
    target_dir = os.path.join(LORA_DIR, category)
    os.makedirs(target_dir, exist_ok=True)
    
    base_path = os.path.join(target_dir, clean_name)
    safetensors_path = f"{base_path}.safetensors"
    info_path = f"{base_path}.civitai.info" 
    forge_json_path = f"{base_path}.json" 
    preview_path = f"{base_path}.preview.png"

    if os.path.exists(safetensors_path): 
        download_status[tracker_name] = "⏭️ Omitido (Localizado en disco)"
        return

    try:
        download_status[tracker_name] = "⏳ Descargando Metadatos..."
        v_url = f"https://civitai.com/api/v1/model-versions/{version['id']}"
        v_info = requests.get(v_url, headers=headers, timeout=15).json()
        with open(info_path, 'w', encoding='utf-8') as f: json.dump(v_info, f, indent=4)
        
        trained_words = version.get('trainedWords', [])
        forge_metadata = {
            "description": model_data.get('description', ""),
            "sd version": version.get('baseModel', "Unknown"),
            "activation text": ", ".join(trained_words),
            "preferred weight": 1.0,
            "notes": f"CivitaiFlow Link: https://civitai.com/models/{model_id}"
        }
        with open(forge_json_path, 'w', encoding='utf-8') as f: json.dump(forge_metadata, f, indent=4)

        if version.get('images'):
            try:
                img_r = requests.get(version['images'][0]['url'], timeout=15)
                with open(preview_path, 'wb') as f: f.write(img_r.content)
            except: pass

        dl_url = f"https://civitai.com/api/download/models/{version['id']}"
        r = requests.get(dl_url + f"?token={api_key}", stream=True, timeout=600)
        
        if r.status_code == 200:
            total_size = int(r.headers.get('content-length', 0))
            downloaded_bytes = 0
            start_time = time.time()
            
            with open(safetensors_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1024*1024): 
                    if chunk:
                        f.write(chunk)
                        downloaded_bytes += len(chunk)
                        elapsed = time.time() - start_time
                        speed_mb = (downloaded_bytes / (1024*1024)) / elapsed if elapsed > 0 else 0
                        
                        if total_size > 0:
                            percent = (downloaded_bytes / total_size) * 100
                            download_status[tracker_name] = f"⬇️ {percent:.1f}%  |  {speed_mb:.1f} MB/s"
                        else:
                            download_status[tracker_name] = f"⬇️ {downloaded_bytes / (1024*1024):.1f} MB  |  {speed_mb:.1f} MB/s"
                            
            download_status[tracker_name] = "✅ Completado"
        else:
            download_status[tracker_name] = f"❌ Error HTTP {r.status_code}"
    except Exception as e:
        download_status[tracker_name] = f"❌ Error Crítico: {str(e)}"

def process_bulk_download_live(text_input, threads):
    global download_status, active_tasks
    
    api_key = shared.opts.data.get("civitai_api_key", "")
    if not api_key: 
        yield "❌ Error: Configura tu API Key en la pestaña Settings."
        return
        
    ids_to_download = parse_civitai_urls(text_input)
    if not ids_to_download: 
        yield "⚠️ No se detectaron Links válidos."
        return

    def task_wrapper(m_id):
        global active_tasks
        download_by_id(m_id, api_key)
        with task_lock:
            active_tasks -= 1

    with task_lock:
        if active_tasks == 0:
            download_status.clear() 
        active_tasks += len(ids_to_download)
        
    def run_downloads():
        with ThreadPoolExecutor(max_workers=int(threads)) as executor:
            for m_id in ids_to_download:
                executor.submit(task_wrapper, m_id)
                
    threading.Thread(target=run_downloads, daemon=True).start()

    while active_tasks > 0:
        time.sleep(0.5) 
        log_lines = [f"📊 TAREAS EN COLA: {active_tasks}\n" + "-"*30]
        for name, status in download_status.items():
            log_lines.append(f"📦 {name}\n   └─ {status}\n")
        yield "\n".join(log_lines)
        
    log_lines = ["🚀 TODAS LAS RÁFAGAS FINALIZADAS\n" + "="*30]
    for name, status in download_status.items():
        log_lines.append(f"📦 {name}\n   └─ {status}\n")
    yield "\n".join(log_lines)

def open_lora_folder():
    os.makedirs(LORA_DIR, exist_ok=True)
    try:
        os.startfile(LORA_DIR)
    except Exception:
        pass

def on_ui_tabs():
    with gr.Blocks(analytics_enabled=False) as civitai_flow_tab:
        with gr.Row():
            
            # Panel Izquierdo (Rediseñado como Dashboard)
            with gr.Column(scale=1):
                gr.Markdown("### 📡 Centro de Mando")
                
                # Grupo visual principal
                with gr.Group():
                    url_input = gr.Textbox(
                        label="📥 Enlaces de Ingesta (Win + V)", 
                        placeholder="Clic derecho en la foto -> Copiar dirección de enlace...", 
                        lines=10
                    )
                    
                    with gr.Row():
                        clear_btn = gr.Button("🗑️ Limpiar", variant="secondary")
                        folder_btn = gr.Button("📂 Ver LoRAs", variant="secondary")
                    
                    download_btn = gr.Button("🚀 Añadir a Cola y Procesar", variant="primary", size="lg")
                
                # Ajustes secundarios colapsables
                with gr.Accordion("⚙️ Configuración de Red", open=False):
                    threads_slider = gr.Slider(minimum=1, maximum=10, step=1, label="Descargas Simultáneas", value=5)
                
                gr.Markdown("<br>") # Espaciador
                
                # Monitor
                status_log = gr.Textbox(label="📊 Monitor de Tráfico (Live)", lines=12)

            # Panel Derecho (Explorador)
            with gr.Column(scale=6):
                gr.HTML('<iframe src="https://civitai.com" style="width: 100%; height: 85vh; border: 2px solid #333; border-radius: 8px;"></iframe>')

        # Eventos
        download_btn.click(fn=process_bulk_download_live, inputs=[url_input, threads_slider], outputs=status_log)
        clear_btn.click(fn=lambda: "", inputs=[], outputs=url_input)
        folder_btn.click(fn=open_lora_folder, inputs=[], outputs=[])
        
    return [(civitai_flow_tab, "CivitaiFlow", "civitai_flow_tab")]

script_callbacks.on_ui_tabs(on_ui_tabs)
