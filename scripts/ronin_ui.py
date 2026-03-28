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

# --- ESTADO GLOBAL ---
DOWNLOAD_STATUS = {}
ACTIVE_TASKS = 0
TASK_LOCK = threading.Lock()
LAST_COPIED_URL = ""
PROCESSED_IDS = set()

def on_ui_settings():
    section = ('civitai_flow', "CivitaiFlow Manager")
    shared.opts.add_option("civitai_api_key", shared.OptionInfo("", "Civitai API Key (Ronin Edition)", gr.Textbox, {"visible": True}, section=section))
script_callbacks.on_ui_settings(on_ui_settings)

def get_windows_clipboard():
    try:
        if not ctypes.windll.user32.OpenClipboard(0): return ""
        handle = ctypes.windll.user32.GetClipboardData(13) 
        if not handle:
            ctypes.windll.user32.CloseClipboard()
            return ""
        pcontents = ctypes.windll.kernel32.GlobalLock(handle)
        if not pcontents: 
            ctypes.windll.user32.CloseClipboard()
            return ""
        data = ctypes.c_wchar_p(pcontents).value
        ctypes.windll.kernel32.GlobalUnlock(handle)
        ctypes.windll.user32.CloseClipboard()
        return data or ""
    except:
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
    global DOWNLOAD_STATUS
    tracker_name = f"ID: {model_id}"
    
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
        DOWNLOAD_STATUS[tracker_name] = f"❌ Error API (¿Civitai caído?): {str(e)}"
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
        else: DOWNLOAD_STATUS[tracker_name] = f"❌ Error HTTP {r.status_code} (Revisa Civitai)"
    except Exception as e: DOWNLOAD_STATUS[tracker_name] = f"❌ Error Crítico: {str(e)}"

# --- LÓGICA CENTRAL EVENT-DRIVEN ---
def process_tick(current_text, is_sniper, is_auto, threads):
    global LAST_COPIED_URL, ACTIVE_TASKS, DOWNLOAD_STATUS, TASK_LOCK, PROCESSED_IDS
    api_key = shared.opts.data.get("civitai_api_key", "")
    current_text = current_text or ""
    
    text_out = gr.update()
    
    # 1. Sniper Mode (Añade a la caja de texto)
    if is_sniper:
        clip = get_windows_clipboard()
        if clip and "civitai.com/models/" in clip and clip != LAST_COPIED_URL:
            LAST_COPIED_URL = clip
            if clip not in current_text:
                current_text = current_text.strip() + "\n" + clip if current_text.strip() else clip
                text_out = current_text

    # 2. Análisis de la Caja de Texto (Detecta Auto-Descarga incluso si pegas manualmente)
    all_ids_in_box = parse_civitai_urls(current_text)
    new_ids = [m_id for m_id in all_ids_in_box if m_id not in PROCESSED_IDS]
    
    if is_auto and new_ids:
        with TASK_LOCK:
            if ACTIVE_TASKS == 0: DOWNLOAD_STATUS.clear()
            ACTIVE_TASKS += len(new_ids)
            for m_id in new_ids: PROCESSED_IDS.add(m_id) # Se marca como procesado
            
        def run_dl(ids_to_dl):
            with ThreadPoolExecutor(max_workers=int(threads)) as executor:
                for m_id in ids_to_dl:
                    download_by_id(m_id, api_key)
                    with TASK_LOCK:
                        global ACTIVE_TASKS
                        ACTIVE_TASKS -= 1
        threading.Thread(target=run_dl, args=(new_ids,), daemon=True).start()

    # 3. Formateo de Consola
    if ACTIVE_TASKS > 0:
        log_lines = [f"📊 TAREAS EN COLA: {ACTIVE_TASKS}\n" + "-"*30]
        log_lines.extend([f"📦 {n}\n   └─ {s}\n" for n, s in DOWNLOAD_STATUS.items()])
        log_out = "\n".join(log_lines)
    elif len(DOWNLOAD_STATUS) > 0:
        log_lines = ["🚀 TODAS LAS TAREAS FINALIZADAS\n" + "="*30]
        log_lines.extend([f"📦 {n}\n   └─ {s}\n" for n, s in DOWNLOAD_STATUS.items()])
        log_out = "\n".join(log_lines)
    else:
        log_out = "Esperando instrucciones..."
        
    return text_out, log_out

def manual_download_trigger(current_text, threads):
    global ACTIVE_TASKS, TASK_LOCK, PROCESSED_IDS
    api_key = shared.opts.data.get("civitai_api_key", "")
    if not api_key: return "❌ Configura tu API Key primero."
    
    all_ids = parse_civitai_urls(current_text or "")
    if not all_ids: return "⚠️ No hay links válidos en la caja."

    with TASK_LOCK:
        if ACTIVE_TASKS == 0: DOWNLOAD_STATUS.clear()
        ACTIVE_TASKS += len(all_ids)
        for m_id in all_ids: PROCESSED_IDS.add(m_id) # Al procesar manual, se marca
        
    def run_dl(ids_to_dl):
        with ThreadPoolExecutor(max_workers=int(threads)) as executor:
            for m_id in ids_to_dl:
                download_by_id(m_id, api_key)
                with TASK_LOCK:
                    global ACTIVE_TASKS
                    ACTIVE_TASKS -= 1
    threading.Thread(target=run_dl, args=(all_ids,), daemon=True).start()
    return "🚀 Forzando descargas manuales..."

def clear_boxes():
    global DOWNLOAD_STATUS, PROCESSED_IDS
    with TASK_LOCK:
        if ACTIVE_TASKS == 0: 
            DOWNLOAD_STATUS.clear()
            PROCESSED_IDS.clear() # Limpiamos el historial para permitir bajar los mismos links de nuevo si se borraron
    return "", ""

def open_lora_folder():
    os.makedirs(LORA_DIR, exist_ok=True)
    try: os.startfile(LORA_DIR)
    except: pass

# --- INTERFAZ UI ---
def on_ui_tabs():
    custom_css = """
    #cf_clear_log_btn { min-width: auto !important; padding: 0px 6px !important; height: 1.5em !important; font-size: 11px !important; margin-left: 10px !important; }
    #cf_poll_btn { display: none !important; position: absolute; width: 0; height: 0; }
    """
    
    with gr.Blocks(analytics_enabled=False, css=custom_css) as civitai_flow_tab:
        
        poll_btn = gr.Button("poll", elem_id="cf_poll_btn")

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

        # --- EVENTOS ---
        poll_btn.click(fn=process_tick, inputs=[url_input, sniper_mode, auto_dl_mode, threads_slider], outputs=[url_input, status_log])
        download_btn.click(fn=manual_download_trigger, inputs=[url_input, threads_slider], outputs=[status_log])
        clear_btn.click(fn=clear_boxes, inputs=[], outputs=[url_input, status_log])
        folder_btn.click(fn=open_lora_folder, inputs=[], outputs=[])
        
        # JS Inyector relajado y seguro (2 segundos, no asfixia al servidor)
        js_onload = """
        () => {
            if (!window.cf_poller_active) {
                window.cf_poller_active = true;
                setInterval(() => {
                    let wrap = document.querySelector('#cf_poll_btn');
                    if (wrap) {
                        let btn = wrap.tagName === 'BUTTON' ? wrap : wrap.querySelector('button');
                        if (btn) btn.click();
                    }
                }, 2000); 
            }
        }
        """
        civitai_flow_tab.load(fn=None, inputs=[], outputs=[], _js=js_onload)
        
    return [(civitai_flow_tab, "CivitaiFlow", "civitai_flow_tab")]

script_callbacks.on_ui_tabs(on_ui_tabs)
