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
EXPIRATION_REGISTRY = {}
ACTIVE_TASKS = 0
TASK_LOCK = threading.Lock()
LAST_CLIPBOARD = ""
PROCESSED_IDS = set()

def on_ui_settings():
    section = ('civitai_flow', "CivitaiFlow Manager")
    shared.opts.add_option("civitai_api_key", shared.OptionInfo("", "Civitai API Key (Ronin Edition)", gr.Textbox, {"visible": True}, section=section))
script_callbacks.on_ui_settings(on_ui_settings)

def get_windows_clipboard():
    try:
        clip_bytes = subprocess.check_output(
            ['powershell', '-NoProfile', '-Command', '[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; Get-Clipboard'],
            creationflags=0x08000000, timeout=2
        )
        text = clip_bytes.decode('utf-8', errors='ignore').strip()
        if len(text) > 300 or "$uiCode" in text or "import os" in text: return ""
        return text
    except: return ""

def parse_civitai_urls(text):
    text = text or ""
    matches = re.findall(r'models/(\d+)', text)
    numbers = re.findall(r'^\d+$', text, re.MULTILINE)
    return list(set(matches + numbers))

def download_by_id(model_id, api_key):
    global DOWNLOAD_STATUS
    tracker_name = f"ID: {model_id}"
    DOWNLOAD_STATUS[tracker_name] = "🔄 Conectando..."
    headers = {"Authorization": f"Bearer {api_key}", "User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(f"https://civitai.com/api/v1/models/{model_id}", headers=headers, timeout=15)
        if r.status_code != 200:
            DOWNLOAD_STATUS[tracker_name] = f"❌ Error API: {r.status_code}"
            return
        model_data = r.json()
        version = model_data['modelVersions'][0] 
        files_list = version.get('files', [])
        primary_file = next((f for f in files_list if f['type'] == 'Model' and f['name'].endswith('.safetensors')), None)
        download_url = primary_file['downloadUrl'] + f"?token={api_key}" if primary_file else f"https://civitai.com/api/download/models/{version['id']}?token={api_key}"
    except Exception as e:
        DOWNLOAD_STATUS[tracker_name] = f"❌ Error: {str(e)[:20]}..."
        return

    clean_name = "".join([c for c in model_data.get('name', tracker_name) if c.isalnum() or c in (' ', '_', '-')]).rstrip()
    category = model_data['tags'][0].replace(' ', '_') if model_data.get('tags') else "General"
    if tracker_name in DOWNLOAD_STATUS: del DOWNLOAD_STATUS[tracker_name]
    tracker_name = clean_name
    
    target_dir = os.path.join(LORA_DIR, category)
    os.makedirs(target_dir, exist_ok=True)
    safetensors_path = os.path.join(target_dir, f"{clean_name}.safetensors")
    
    if os.path.exists(safetensors_path): 
        DOWNLOAD_STATUS[tracker_name] = "⏭️ Ya existe"
        return

    try:
        forge_json = {"description": model_data.get('description', ""), "sd version": version.get('baseModel', "Unknown"), "activation text": ", ".join(version.get('trainedWords', [])), "preferred weight": 1.0}
        with open(os.path.join(target_dir, f"{clean_name}.json"), 'w', encoding='utf-8') as f: json.dump(forge_json, f, indent=4)
        r = requests.get(download_url, headers=headers, stream=True, timeout=600)
        if r.status_code == 200:
            total_size = int(r.headers.get('content-length', 0))
            dl_bytes, start = 0, time.time()
            with open(safetensors_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1024*1024):
                    if chunk:
                        f.write(chunk)
                        dl_bytes += len(chunk)
                        elapsed = time.time() - start
                        speed = (dl_bytes / (1024*1024)) / elapsed if elapsed > 0 else 0
                        DOWNLOAD_STATUS[tracker_name] = f"⬇️ {(dl_bytes/total_size)*100:.1f}% | {speed:.1f} MB/s"
            DOWNLOAD_STATUS[tracker_name] = "✅ OK"
        else: DOWNLOAD_STATUS[tracker_name] = f"❌ HTTP {r.status_code}"
    except Exception as e: DOWNLOAD_STATUS[tracker_name] = f"❌ Error: {str(e)[:20]}"

def master_tick(current_text, is_sniper, is_auto, threads):
    global LAST_CLIPBOARD, ACTIVE_TASKS, DOWNLOAD_STATUS, TASK_LOCK, PROCESSED_IDS, EXPIRATION_REGISTRY
    api_key = shared.opts.data.get("civitai_api_key", "")
    current_text = current_text or ""
    text_update = gr.update()
    
    # 1. Sniper Automático
    if is_sniper:
        clip = get_windows_clipboard()
        if clip and "civitai.com/models/" in clip and clip != LAST_CLIPBOARD:
            LAST_CLIPBOARD = clip
            if clip not in current_text:
                current_text = current_text.strip() + "\n" + clip if current_text.strip() else clip
                text_update = current_text

    # 2. Motor de Reacción Automática (Auto-DL)
    if is_auto:
        all_ids = parse_civitai_urls(current_text)
        new_ids = [m_id for m_id in all_ids if m_id not in PROCESSED_IDS]
        if new_ids:
            with TASK_LOCK:
                ACTIVE_TASKS += len(new_ids)
                for m_id in new_ids: PROCESSED_IDS.add(m_id)
            def run_queue(ids):
                with ThreadPoolExecutor(max_workers=int(threads)) as executor:
                    for m_id in ids:
                        download_by_id(m_id, api_key)
                        with TASK_LOCK:
                            global ACTIVE_TASKS
                            ACTIVE_TASKS -= 1
            threading.Thread(target=run_queue, args=(new_ids,), daemon=True).start()
            text_update = "" # Purga inmediata tras ingesta

    # 3. Limpieza de logs individual (TTL 8s)
    now = time.time()
    for name, status in list(DOWNLOAD_STATUS.items()):
        if "✅ OK" in status or "⏭️ Ya existe" in status or "❌ Error" in status:
            if name not in EXPIRATION_REGISTRY: EXPIRATION_REGISTRY[name] = now
            elif now - EXPIRATION_REGISTRY[name] > 8:
                del DOWNLOAD_STATUS[name]
                del EXPIRATION_REGISTRY[name]

    if ACTIVE_TASKS > 0 or DOWNLOAD_STATUS:
        log_out = []
        if ACTIVE_TASKS > 0: log_out.append(f"📊 DESCARGAS ACTIVAS: {ACTIVE_TASKS}\n" + "-"*25)
        log_out.extend([f"📦 {n[:32]}\n  └ {s}\n" for n, s in DOWNLOAD_STATUS.items()])
        return text_update, "\n".join(log_out)
    
    return text_update, "😴 Sistema en espera... Copia un link de Civitai para despertar."

def reset_all():
    global DOWNLOAD_STATUS, PROCESSED_IDS, LAST_CLIPBOARD, EXPIRATION_REGISTRY
    with TASK_LOCK:
        DOWNLOAD_STATUS.clear()
        PROCESSED_IDS.clear()
        EXPIRATION_REGISTRY.clear()
        LAST_CLIPBOARD = ""
    return "", "Caché reiniciada."

def open_loras():
    os.makedirs(LORA_DIR, exist_ok=True)
    os.startfile(LORA_DIR)

def on_ui_tabs():
    with gr.Blocks(analytics_enabled=False) as cf_tab:
        timer = gr.Timer(1.5)
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### 📡 CivitaiFlow v20 (Full-Auto)")
                with gr.Group():
                    with gr.Row():
                        sniper = gr.Checkbox(label="🎯 Sniper", value=True)
                        auto = gr.Checkbox(label="⚡ Auto-DL", value=True)
                    url_box = gr.Textbox(label="📥 Puente de Ingesta", lines=1, placeholder="Sniper armado...")
                    with gr.Row():
                        btn_clear = gr.Button("🗑️ Reset", variant="secondary")
                        btn_folder = gr.Button("📂 Abrir Lora", variant="secondary")
                
                with gr.Accordion("⚙️ Red", open=False):
                    th_slider = gr.Slider(1, 10, 5, step=1, label="Hilos Simultáneos")
                
                gr.Markdown("<br>")
                log_box = gr.Textbox(label="📊 Monitor de Tráfico (Live)", lines=28, interactive=False)

            with gr.Column(scale=6):
                gr.HTML('<iframe src="https://civitai.com" style="width: 100%; height: 90vh; border: 2px solid #222; border-radius: 12px;"></iframe>')

        timer.tick(fn=master_tick, inputs=[url_box, sniper, auto, th_slider], outputs=[url_box, log_box])
        btn_clear.click(fn=reset_all, outputs=[url_box, log_box])
        btn_folder.click(fn=open_loras)
    return [(cf_tab, "CivitaiFlow", "cf_tab")]

script_callbacks.on_ui_tabs(on_ui_tabs)
