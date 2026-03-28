import os
import requests
import json
import re
import time
import threading
import subprocess
import modules.scripts as scripts
import gradio as gr
from modules import paths, shared, script_callbacks
from concurrent.futures import ThreadPoolExecutor

LORA_DIR = os.path.join(paths.models_path, "Lora")

# --- ESTADO GLOBAL ---
DOWNLOAD_STATUS = {}
ACTIVE_TASKS = 0
TASK_LOCK = threading.Lock()
LAST_CLIPBOARD = ""
PROCESSED_IDS = set()

def on_ui_settings():
    section = ('civitai_flow', "CivitaiFlow Manager")
    shared.opts.add_option("civitai_api_key", shared.OptionInfo("", "Civitai API Key (Ronin Edition)", gr.Textbox, {"visible": True}, section=section))
script_callbacks.on_ui_settings(on_ui_settings)

# --- HOOK DE PORTAPAPELES (NIVEL SYSADMIN - 100% AISLADO) ---
def get_windows_clipboard():
    try:
        # Usa subprocess para llamar a PowerShell. creationflags=0x08000000 evita que salga la ventana negra.
        # Esto aísla la memoria completamente del hilo de Python. Imposible crashear Forge.
        clip_bytes = subprocess.check_output(
            ['powershell', '-NoProfile', '-Command', 'Get-Clipboard'],
            creationflags=0x08000000, 
            timeout=2
        )
        return clip_bytes.decode('utf-8', errors='ignore').strip()
    except Exception:
        return ""

def parse_civitai_urls(text):
    text = text or ""
    matches = re.findall(r'models/(\d+)', text)
    numbers = re.findall(r'^\d+$', text, re.MULTILINE)
    return list(set(matches + numbers))

# --- MOTOR DE DESCARGA ---
def download_by_id(model_id, api_key):
    global DOWNLOAD_STATUS
    tracker_name = f"ID: {model_id}"
    
    DOWNLOAD_STATUS[tracker_name] = "🔄 Obteniendo metadata..."
    headers = {"Authorization": f"Bearer {api_key}", "User-Agent": "Mozilla/5.0"}
    
    try:
        model_url = f"https://civitai.com/api/v1/models/{model_id}"
        r = requests.get(model_url, headers=headers, timeout=15)
        if r.status_code != 200:
            DOWNLOAD_STATUS[tracker_name] = f"❌ Error API: HTTP {r.status_code} (Revisa Civitai)"
            return
        model_data = r.json()
        
        if 'modelVersions' not in model_data: 
            DOWNLOAD_STATUS[tracker_name] = "❌ Error: Modelo no encontrado"
            return
        version = model_data['modelVersions'][0] 
        
        files_list = version.get('files', [])
        primary_file = next((f for f in files_list if f['type'] == 'Model' and f['name'].endswith('.safetensors')), None)
        download_url = primary_file['downloadUrl'] + f"?token={api_key}" if primary_file else f"https://civitai.com/api/download/models/{version['id']}?token={api_key}"
    except Exception as e:
        DOWNLOAD_STATUS[tracker_name] = f"❌ Error de Conexión: {str(e)}"
        return

    model_title = model_data.get('name', f"Civitai_Model_{model_id}")
    clean_name = "".join([c for c in model_title if c.isalnum() or c in (' ', '_', '-')]).rstrip()
    category = model_data['tags'][0].replace(' ', '_').replace('/', '_') if model_data.get('tags') else "General"
    
    del DOWNLOAD_STATUS[tracker_name]
    tracker_name = clean_name
    
    target_dir = os.path.join(LORA_DIR, category)
    os.makedirs(target_dir, exist_ok=True)
    base_path = os.path.join(target_dir, clean_name)
    safetensors_path = f"{base_path}.safetensors"
    
    if os.path.exists(safetensors_path): 
        DOWNLOAD_STATUS[tracker_name] = "⏭️ Omitido (Ya existe)"
        return

    try:
        DOWNLOAD_STATUS[tracker_name] = "⏳ Metadatos..."
        v_url = f"https://civitai.com/api/v1/model-versions/{version['id']}"
        with open(f"{base_path}.civitai.info", 'w', encoding='utf-8') as f: json.dump(requests.get(v_url, headers=headers, timeout=15).json(), f, indent=4)
        
        forge_metadata = {"description": model_data.get('description', ""), "sd version": version.get('baseModel', "Unknown"), "activation text": ", ".join(version.get('trainedWords', [])), "preferred weight": 1.0, "notes": f"CivitaiFlow Link: https://civitai.com/models/{model_id}"}
        with open(f"{base_path}.json", 'w', encoding='utf-8') as f: json.dump(forge_metadata, f, indent=4)

        if version.get('images'):
            try:
                img_r = requests.get(version['images'][0]['url'], timeout=15)
                with open(f"{base_path}.preview.png", 'wb') as f: f.write(img_r.content)
            except: pass

        r = requests.get(download_url, headers=headers, stream=True, timeout=600)
        if r.status_code == 200:
            total_size = int(r.headers.get('content-length', 0))
            downloaded_bytes, start_time = 0, time.time()
            
            with open(safetensors_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1024*1024): 
                    if chunk:
                        f.write(chunk)
                        downloaded_bytes += len(chunk)
                        elapsed = time.time() - start_time
                        speed_mb = (downloaded_bytes / (1024*1024)) / elapsed if elapsed > 0 else 0
                        DOWNLOAD_STATUS[tracker_name] = f"⬇️ {(downloaded_bytes/total_size)*100:.1f}% | {speed_mb:.1f} MB/s" if total_size > 0 else f"⬇️ {downloaded_bytes/(1024*1024):.1f} MB | {speed_mb:.1f} MB/s"
            DOWNLOAD_STATUS[tracker_name] = "✅ Completado"
        else: DOWNLOAD_STATUS[tracker_name] = f"❌ Error HTTP {r.status_code}"
    except Exception as e: DOWNLOAD_STATUS[tracker_name] = f"❌ Error Crítico: {str(e)}"

# --- GENERADORES (UI Seguro) ---
def sniper_loop(is_sniper, is_auto, current_text, threads):
    global LAST_CLIPBOARD, ACTIVE_TASKS, TASK_LOCK, PROCESSED_IDS
    api_key = shared.opts.data.get("civitai_api_key", "")
    current_text = current_text or ""

    if not is_sniper:
        yield current_text, "🎯 Modo Sniper [Desactivado]"
        return

    yield current_text, "🎯 Modo Sniper [ON] - Escuchando portapapeles..."

    while is_sniper:
        time.sleep(1.5) # Pulso suave
        changed = False
        log_out = ""

        clip = get_windows_clipboard()
        if clip and "civitai.com/models/" in clip and clip != LAST_CLIPBOARD:
            LAST_CLIPBOARD = clip
            if clip not in current_text:
                current_text = current_text.strip() + "\n" + clip if current_text.strip() else clip
                changed = True

                if is_auto:
                    ids = parse_civitai_urls(clip)
                    new_ids = [i for i in ids if i not in PROCESSED_IDS]
                    if new_ids:
                        with TASK_LOCK:
                            if ACTIVE_TASKS == 0: DOWNLOAD_STATUS.clear()
                            ACTIVE_TASKS += len(new_ids)
                            for i in new_ids: PROCESSED_IDS.add(i)

                        def run_dl(dl_ids):
                            with ThreadPoolExecutor(max_workers=int(threads)) as executor:
                                for m_id in dl_ids:
                                    download_by_id(m_id, api_key)
                                    with TASK_LOCK:
                                        global ACTIVE_TASKS
                                        ACTIVE_TASKS -= 1
                        threading.Thread(target=run_dl, args=(new_ids,), daemon=True).start()

        if ACTIVE_TASKS > 0:
            log_lines = [f"📊 TAREAS EN COLA: {ACTIVE_TASKS}\n" + "-"*30]
            log_lines.extend([f"📦 {n}\n   └─ {s}\n" for n, s in DOWNLOAD_STATUS.items()])
            log_out = "\n".join(log_lines)
            changed = True
        elif len(DOWNLOAD_STATUS) > 0:
            log_lines = ["🚀 TODAS LAS TAREAS FINALIZADAS\n" + "="*30]
            log_lines.extend([f"📦 {n}\n   └─ {s}\n" for n, s in DOWNLOAD_STATUS.items()])
            log_out = "\n".join(log_lines)
            changed = True

        if changed:
            yield current_text, log_out

def process_manual(current_text, threads):
    global ACTIVE_TASKS, TASK_LOCK, PROCESSED_IDS
    api_key = shared.opts.data.get("civitai_api_key", "")
    if not api_key:
        yield "❌ Error: Configura tu API Key en la pestaña Settings."
        return

    current_text = current_text or ""
    ids = parse_civitai_urls(current_text)
    new_ids = [i for i in ids if i not in PROCESSED_IDS]

    if not new_ids:
        yield "⚠️ No hay links nuevos por procesar."
        return

    with TASK_LOCK:
        if ACTIVE_TASKS == 0: DOWNLOAD_STATUS.clear()
        ACTIVE_TASKS += len(new_ids)
        for i in new_ids: PROCESSED_IDS.add(i)

    def run_dl(dl_ids):
        with ThreadPoolExecutor(max_workers=int(threads)) as executor:
            for m_id in dl_ids:
                download_by_id(m_id, api_key)
                with TASK_LOCK:
                    global ACTIVE_TASKS
                    ACTIVE_TASKS -= 1
    threading.Thread(target=run_dl, args=(new_ids,), daemon=True).start()

    while ACTIVE_TASKS > 0:
        time.sleep(1)
        log_lines = [f"📊 TAREAS EN COLA: {ACTIVE_TASKS}\n" + "-"*30]
        log_lines.extend([f"📦 {n}\n   └─ {s}\n" for n, s in DOWNLOAD_STATUS.items()])
        yield "\n".join(log_lines)

    log_lines = ["🚀 TODAS LAS TAREAS FINALIZADAS\n" + "="*30]
    log_lines.extend([f"📦 {n}\n   └─ {s}\n" for n, s in DOWNLOAD_STATUS.items()])
    yield "\n".join(log_lines)

def clear_boxes():
    global DOWNLOAD_STATUS, PROCESSED_IDS, LAST_CLIPBOARD
    with TASK_LOCK:
        if ACTIVE_TASKS == 0: 
            DOWNLOAD_STATUS.clear()
            PROCESSED_IDS.clear()
            LAST_CLIPBOARD = ""
    return "", ""

def open_lora_folder():
    os.makedirs(LORA_DIR, exist_ok=True)
    try: os.startfile(LORA_DIR)
    except: pass

# --- INTERFAZ UI ---
def on_ui_tabs():
    custom_css = "#cf_clear_log_btn { min-width: auto !important; padding: 0px 6px !important; height: 1.5em !important; font-size: 11px !important; margin-left: 10px !important; }"
    
    with gr.Blocks(analytics_enabled=False, css=custom_css) as civitai_flow_tab:

        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### 📡 Centro de Mando")
                with gr.Group():
                    with gr.Row():
                        sniper_mode = gr.Checkbox(label="🎯 Modo Sniper", value=False)
                        auto_dl_mode = gr.Checkbox(label="⚡ Auto-Descargar", value=False)
                    url_input = gr.Textbox(label="📥 Enlaces de Ingesta", lines=10)
                    with gr.Row():
                        clear_btn = gr.Button("🗑️ Limpiar Cajas", variant="secondary")
                        folder_btn = gr.Button("📂 Ver LoRAs", variant="secondary")
                    download_btn = gr.Button("🚀 Procesar Lista Manualmente", variant="primary", size="lg")
                
                with gr.Accordion("⚙️ Configuración de Red", open=False):
                    threads_slider = gr.Slider(minimum=1, maximum=10, step=1, label="Descargas Simultáneas", value=5)
                
                gr.Markdown("<br>")
                with gr.Row(variant="compact"):
                    gr.Markdown("#### 📊 Monitor de Tráfico")
                    clear_log_btn = gr.Button("Limpiar 🗑️", variant="secondary", elem_id="cf_clear_log_btn")
                status_log = gr.Textbox(label="Status Log Output", show_label=False, lines=12)

            with gr.Column(scale=6):
                gr.HTML('<iframe src="https://civitai.com" style="width: 100%; height: 85vh; border: 2px solid #333; border-radius: 8px;"></iframe>')

        # --- EVENTOS ---
        sniper_mode.change(fn=sniper_loop, inputs=[sniper_mode, auto_dl_mode, url_input, threads_slider], outputs=[url_input, status_log])
        download_btn.click(fn=process_manual, inputs=[url_input, threads_slider], outputs=[status_log])
        clear_btn.click(fn=clear_boxes, inputs=[], outputs=[url_input, status_log])
        folder_btn.click(fn=open_lora_folder, inputs=[], outputs=[])
        clear_log_btn.click(fn=clear_boxes, inputs=[], outputs=[url_input, status_log])
        
    return [(civitai_flow_tab, "CivitaiFlow", "civitai_flow_tab")]

script_callbacks.on_ui_tabs(on_ui_tabs)
