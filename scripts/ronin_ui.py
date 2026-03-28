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

# --- VARIABLES GLOBALES ---
download_status = {}
active_tasks = 0
task_lock = threading.Lock()
last_copied_url = ""
last_log_text = ""

def on_ui_settings():
    section = ('civitai_flow', "CivitaiFlow Manager")
    shared.opts.add_option("civitai_api_key", shared.OptionInfo("", "Civitai API Key (Ronin Edition)", gr.Textbox, {"visible": True}, section=section))
script_callbacks.on_ui_settings(on_ui_settings)

# --- HOOK NATIVO DE WINDOWS (SEGURO) ---
def get_windows_clipboard():
    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        
        if not user32.OpenClipboard(0): return ""
        
        handle = user32.GetClipboardData(13) 
        if not handle:
            user32.CloseClipboard()
            return ""
            
        pcontents = kernel32.GlobalLock(handle)
        if not pcontents: 
            user32.CloseClipboard()
            return ""
            
        data = ctypes.c_wchar_p(pcontents).value
        
        kernel32.GlobalUnlock(handle)
        user32.CloseClipboard()
        return data or ""
    except Exception:
        try: ctypes.windll.user32.CloseClipboard()
        except: pass
        return ""

def parse_civitai_urls(text):
    text = text or ""
    matches = re.findall(r'models/(\d+)', text)
    numbers = re.findall(r'^\d+$', text, re.MULTILINE)
    return list(set(matches + numbers))

# --- MOTOR DE DESCARGA ---
def download_by_id(model_id, api_key):
    global download_status
    tracker_name = f"ID: {model_id}"
    
    if tracker_name in download_status and "⬇️" in download_status[tracker_name]: return

    download_status[tracker_name] = "🔄 Obteniendo metadata..."
    headers = {"Authorization": f"Bearer {api_key}", "User-Agent": "Mozilla/5.0"}
    
    try:
        model_url = f"https://civitai.com/api/v1/models/{model_id}"
        model_data = requests.get(model_url, headers=headers, timeout=15).json()
        if 'modelVersions' not in model_data: 
            download_status[tracker_name] = "❌ Error: Modelo no encontrado"
            return
        version = model_data['modelVersions'][0] 
        
        files_list = version.get('files', [])
        primary_file = next((f for f in files_list if f['type'] == 'Model' and f['name'].endswith('.safetensors')), None)
        download_url = primary_file['downloadUrl'] + f"?token={api_key}" if primary_file else f"https://civitai.com/api/download/models/{version['id']}?token={api_key}"
    except Exception as e:
        download_status[tracker_name] = f"❌ Error API: {str(e)}"
        return

    model_title = model_data.get('name', f"Civitai_Model_{model_id}")
    clean_name = "".join([c for c in model_title if c.isalnum() or c in (' ', '_', '-')]).rstrip()
    category = model_data['tags'][0].replace(' ', '_').replace('/', '_') if model_data.get('tags') else "General"
    
    if tracker_name in download_status: del download_status[tracker_name]
    tracker_name = clean_name
    
    target_dir = os.path.join(LORA_DIR, category)
    os.makedirs(target_dir, exist_ok=True)
    base_path = os.path.join(target_dir, clean_name)
    safetensors_path = f"{base_path}.safetensors"
    
    if os.path.exists(safetensors_path): 
        download_status[tracker_name] = "⏭️ Omitido (Localizado en disco)"
        return

    try:
        download_status[tracker_name] = "⏳ Metadatos..."
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
                        download_status[tracker_name] = f"⬇️ {(downloaded_bytes/total_size)*100:.1f}% | {speed_mb:.1f} MB/s" if total_size > 0 else f"⬇️ {downloaded_bytes/(1024*1024):.1f} MB | {speed_mb:.1f} MB/s"
            download_status[tracker_name] = "✅ Completado"
        else: download_status[tracker_name] = f"❌ Error HTTP {r.status_code}"
    except Exception as e: download_status[tracker_name] = f"❌ Error Crítico: {str(e)}"

# --- MOTOR DE POLLING NATIVO (CRON JOB) ---
def universal_poller(current_text, is_sniper, is_auto, threads):
    global last_copied_url, active_tasks, download_status, task_lock, last_log_text
    api_key = shared.opts.data.get("civitai_api_key", "")
    current_text = current_text or ""
    
    text_out = gr.update()
    log_out = gr.update()
    
    # 1. Sniper Automático
    if is_sniper:
        clip = get_windows_clipboard()
        if clip and isinstance(clip, str) and clip != last_copied_url and "civitai.com/models/" in clip:
            last_copied_url = clip
            current_text = current_text.strip() + "\n" + clip if current_text.strip() else clip
            text_out = current_text # Manda el texto actualizado a la caja
            
            if is_auto:
                ids = parse_civitai_urls(clip)
                if ids:
                    with task_lock:
                        if active_tasks == 0: download_status.clear()
                        active_tasks += len(ids)
                    def run_dl(ids_to_dl):
                        with ThreadPoolExecutor(max_workers=int(threads)) as executor:
                            for m_id in ids_to_dl:
                                download_by_id(m_id, api_key)
                                with task_lock:
                                    global active_tasks
                                    active_tasks -= 1
                    threading.Thread(target=run_dl, args=(ids,), daemon=True).start()
                        
    # 2. Refresco de Consola (Solo actualiza si hay cambios para no trabar la UI)
    new_log = ""
    if active_tasks > 0:
        log_lines = [f"📊 TAREAS EN COLA: {active_tasks}\n" + "-"*30]
        log_lines.extend([f"📦 {n}\n   └─ {s}\n" for n, s in download_status.items()])
        new_log = "\n".join(log_lines)
    elif len(download_status) > 0:
        log_lines = ["🚀 TODAS LAS RÁFAGAS FINALIZADAS\n" + "="*30]
        log_lines.extend([f"📦 {n}\n   └─ {s}\n" for n, s in download_status.items()])
        new_log = "\n".join(log_lines)
        
    if new_log != last_log_text:
        last_log_text = new_log
        log_out = new_log
        
    return text_out, log_out

def manual_download_trigger(text_input, threads):
    global download_status, active_tasks, task_lock
    api_key = shared.opts.data.get("civitai_api_key", "")
    if not api_key: 
        download_status["API_KEY"] = "❌ Error: Configura tu API Key."
        return gr.update()
    
    text_input = text_input or ""
    ids_to_download = parse_civitai_urls(text_input)
    if not ids_to_download: return gr.update()

    with task_lock:
        if active_tasks == 0: download_status.clear() 
        active_tasks += len(ids_to_download)
        
    def run_downloads(ids_to_dl):
        with ThreadPoolExecutor(max_workers=int(threads)) as executor:
            for m_id in ids_to_dl:
                download_by_id(m_id, api_key)
                with task_lock:
                    global active_tasks
                    active_tasks -= 1
                    
    threading.Thread(target=run_downloads, args=(ids_to_download,), daemon=True).start()
    return gr.update()

def clear_log_dashboard():
    global download_status, last_log_text
    with task_lock:
        if active_tasks == 0: 
            download_status.clear()
            last_log_text = ""

def open_lora_folder():
    os.makedirs(LORA_DIR, exist_ok=True)
    try: os.startfile(LORA_DIR)
    except: pass

# --- INTERFAZ UI ---
def on_ui_tabs():
    custom_css = """
    #cf_clear_log_btn { min-width: auto !important; padding: 0px 6px !important; height: 1.5em !important; font-size: 11px !important; margin-left: 10px !important; }
    """
    
    with gr.Blocks(analytics_enabled=False, css=custom_css) as civitai_flow_tab:
        
        # CRON JOB NATIVO: Ejecuta el poller cada 1.5 segundos en background sin JS
        poller_timer = gr.Timer(1.5, active=True)

        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### 📡 Centro de Mando")
                with gr.Group():
                    with gr.Row():
                        sniper_mode = gr.Checkbox(label="🎯 Modo Sniper", value=False)
                        auto_dl_mode = gr.Checkbox(label="⚡ Auto-Descargar", value=False)
                    url_input = gr.Textbox(label="📥 Enlaces de Ingesta", placeholder="Activa Sniper y Auto-Descargar. Navega, copia un enlace y observa...", lines=10)
                    with gr.Row():
                        clear_btn = gr.Button("🗑️ Limpiar Caja", variant="secondary")
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

        # --- EVENTOS DE CONEXIÓN ---
        poller_timer.tick(fn=universal_poller, inputs=[url_input, sniper_mode, auto_dl_mode, threads_slider], outputs=[url_input, status_log])
        
        download_btn.click(fn=manual_download_trigger, inputs=[url_input, threads_slider], outputs=[])
        clear_btn.click(fn=lambda: "", inputs=[], outputs=url_input)
        folder_btn.click(fn=open_lora_folder, inputs=[], outputs=[])
        clear_log_btn.click(fn=clear_log_dashboard, inputs=[], outputs=[])
        
    return [(civitai_flow_tab, "CivitaiFlow", "civitai_flow_tab")]

script_callbacks.on_ui_tabs(on_ui_tabs)
