import os
import requests
import json
import re
import time
import threading
import ctypes
import modules.scripts as scripts
import gradio as gr
from modules import paths, shared, script_callbacks
from concurrent.futures import ThreadPoolExecutor

LORA_DIR = os.path.join(paths.models_path, "Lora")

# --- ESTADO GLOBAL (Independiente de la UI) ---
SYS_STATE = {
    "sniper_on": False,
    "auto_on": False,
    "ui_text": "",
    "threads": 5
}
DOWNLOAD_STATUS = {}
ACTIVE_TASKS = 0
TASK_LOCK = threading.Lock()
LAST_CLIP = ""

def on_ui_settings():
    section = ('civitai_flow', "CivitaiFlow Manager")
    shared.opts.add_option("civitai_api_key", shared.OptionInfo("", "Civitai API Key (Ronin Edition)", gr.Textbox, {"visible": True}, section=section))
script_callbacks.on_ui_settings(on_ui_settings)

def parse_civitai_urls(text):
    text = text or ""
    matches = re.findall(r'models/(\d+)', text)
    numbers = re.findall(r'^\d+$', text, re.MULTILINE)
    return list(set(matches + numbers))

# --- MOTOR DE DESCARGA ---
def download_by_id(model_id, api_key):
    global DOWNLOAD_STATUS
    tracker_name = f"ID: {model_id}"
    
    if tracker_name in DOWNLOAD_STATUS and "⬇️" in DOWNLOAD_STATUS[tracker_name]: return

    DOWNLOAD_STATUS[tracker_name] = "🔄 Obteniendo metadata..."
    headers = {"Authorization": f"Bearer {api_key}", "User-Agent": "Mozilla/5.0"}
    
    try:
        model_url = f"https://civitai.com/api/v1/models/{model_id}"
        model_data = requests.get(model_url, headers=headers, timeout=15).json()
        if 'modelVersions' not in model_data: 
            DOWNLOAD_STATUS[tracker_name] = "❌ Error: Modelo no encontrado"
            return
        version = model_data['modelVersions'][0] 
        
        files_list = version.get('files', [])
        primary_file = next((f for f in files_list if f['type'] == 'Model' and f['name'].endswith('.safetensors')), None)
        download_url = primary_file['downloadUrl'] + f"?token={api_key}" if primary_file else f"https://civitai.com/api/download/models/{version['id']}?token={api_key}"
    except Exception as e:
        DOWNLOAD_STATUS[tracker_name] = f"❌ Error API: {str(e)}"
        return

    model_title = model_data.get('name', f"Civitai_Model_{model_id}")
    clean_name = "".join([c for c in model_title if c.isalnum() or c in (' ', '_', '-')]).rstrip()
    category = model_data['tags'][0].replace(' ', '_').replace('/', '_') if model_data.get('tags') else "General"
    
    if tracker_name in DOWNLOAD_STATUS: del DOWNLOAD_STATUS[tracker_name]
    tracker_name = clean_name
    
    target_dir = os.path.join(LORA_DIR, category)
    os.makedirs(target_dir, exist_ok=True)
    base_path = os.path.join(target_dir, clean_name)
    safetensors_path = f"{base_path}.safetensors"
    
    if os.path.exists(safetensors_path): 
        DOWNLOAD_STATUS[tracker_name] = "⏭️ Omitido (Localizado en disco)"
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

def worker_thread(m_id, api_key):
    global ACTIVE_TASKS
    download_by_id(m_id, api_key)
    with TASK_LOCK:
        ACTIVE_TASKS -= 1

# --- DEMONIO AISLADO EN SEGUNDO PLANO (A PRUEBA DE CRASHEOS) ---
def clipboard_daemon():
    global LAST_CLIP, ACTIVE_TASKS
    while True:
        time.sleep(1)
        if not SYS_STATE["sniper_on"]: continue

        try:
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            clip = ""
            if user32.OpenClipboard(0):
                handle = user32.GetClipboardData(13)
                if handle:
                    pcontents = kernel32.GlobalLock(handle)
                    if pcontents:
                        clip = ctypes.c_wchar_p(pcontents).value
                        kernel32.GlobalUnlock(handle)
                user32.CloseClipboard()
        except: clip = ""

        if clip and isinstance(clip, str) and "civitai.com/models/" in clip and clip != LAST_CLIP:
            LAST_CLIP = clip
            curr = SYS_STATE["ui_text"].strip()
            SYS_STATE["ui_text"] = curr + "\n" + clip if curr else clip

            if SYS_STATE["auto_on"]:
                ids = parse_civitai_urls(clip)
                if ids:
                    api_key = shared.opts.data.get("civitai_api_key", "")
                    with TASK_LOCK:
                        if ACTIVE_TASKS == 0: DOWNLOAD_STATUS.clear()
                        ACTIVE_TASKS += len(ids)
                    for m_id in ids:
                        threading.Thread(target=worker_thread, args=(m_id, api_key), daemon=True).start()

# Arrancar el demonio maestro UNA SOLA VEZ al cargar la extensión
threading.Thread(target=clipboard_daemon, daemon=True).start()

# --- SINCRONIZADOR DE INTERFAZ ---
LAST_UI_TEXT = ""
LAST_LOG_TEXT = ""

def sync_ui():
    global LAST_UI_TEXT, LAST_LOG_TEXT
    text_up, log_up = gr.update(), gr.update()

    if SYS_STATE["ui_text"] != LAST_UI_TEXT:
        LAST_UI_TEXT = SYS_STATE["ui_text"]
        text_up = SYS_STATE["ui_text"]

    log_lines = []
    if ACTIVE_TASKS > 0:
        log_lines = [f"📊 TAREAS EN COLA: {ACTIVE_TASKS}\n" + "-"*30]
        log_lines.extend([f"📦 {n}\n   └─ {s}\n" for n, s in DOWNLOAD_STATUS.items()])
        log_str = "\n".join(log_lines)
    elif len(DOWNLOAD_STATUS) > 0:
        log_lines = ["🚀 TODAS LAS RÁFAGAS FINALIZADAS\n" + "="*30]
        log_lines.extend([f"📦 {n}\n   └─ {s}\n" for n, s in DOWNLOAD_STATUS.items()])
        log_str = "\n".join(log_lines)
    else:
        log_str = "🎯 Modo Sniper [ON] - Escuchando el portapapeles..." if SYS_STATE["sniper_on"] else "Modo de espera..."

    if log_str != LAST_LOG_TEXT:
        LAST_LOG_TEXT = log_str
        log_up = log_str

    return text_up, log_up

# Actualizadores de variables globales desde la UI
def update_sniper(val): SYS_STATE["sniper_on"] = val
def update_auto(val): SYS_STATE["auto_on"] = val
def update_text(val): SYS_STATE["ui_text"] = val
def update_threads(val): SYS_STATE["threads"] = val

def manual_download_trigger():
    global ACTIVE_TASKS
    api_key = shared.opts.data.get("civitai_api_key", "")
    if not api_key: return
    
    ids_to_download = parse_civitai_urls(SYS_STATE["ui_text"])
    if not ids_to_download: return

    with TASK_LOCK:
        if ACTIVE_TASKS == 0: DOWNLOAD_STATUS.clear() 
        ACTIVE_TASKS += len(ids_to_download)
        
    for m_id in ids_to_download:
        threading.Thread(target=worker_thread, args=(m_id, api_key), daemon=True).start()

def clear_boxes():
    global LAST_UI_TEXT, LAST_LOG_TEXT
    SYS_STATE["ui_text"] = ""
    LAST_UI_TEXT = ""
    with TASK_LOCK:
        if ACTIVE_TASKS == 0: 
            DOWNLOAD_STATUS.clear()
            LAST_LOG_TEXT = ""

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
                status_log = gr.Textbox(label="Status Log Output", show_label=False, lines=12)

            with gr.Column(scale=6):
                gr.HTML('<iframe src="https://civitai.com" style="width: 100%; height: 85vh; border: 2px solid #333; border-radius: 8px;"></iframe>')

        # Conectar UI con el Estado Global
        sniper_mode.change(fn=update_sniper, inputs=[sniper_mode])
        auto_dl_mode.change(fn=update_auto, inputs=[auto_dl_mode])
        url_input.change(fn=update_text, inputs=[url_input])
        threads_slider.change(fn=update_threads, inputs=[threads_slider])

        # Sincronizador de Interfaz (Seguro, cada 1 segundo)
        civitai_flow_tab.load(fn=sync_ui, inputs=[], outputs=[url_input, status_log], every=1)
        
        # Botones
        download_btn.click(fn=manual_download_trigger, inputs=[], outputs=[])
        clear_btn.click(fn=clear_boxes, inputs=[], outputs=[])
        folder_btn.click(fn=open_lora_folder, inputs=[], outputs=[])
        
    return [(civitai_flow_tab, "CivitaiFlow", "civitai_flow_tab")]

script_callbacks.on_ui_tabs(on_ui_tabs)
