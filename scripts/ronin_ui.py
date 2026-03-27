import os
import requests
import json
import modules.scripts as scripts
import gradio as gr
from modules import paths, shared, script_callbacks
from concurrent.futures import ThreadPoolExecutor

LORA_DIR = os.path.join(paths.models_path, "Lora")

def on_ui_settings():
    section = ('civitai_flow', "CivitaiFlow Manager")
    shared.opts.add_option("civitai_api_key", shared.OptionInfo("", "Civitai API Key (Ronin Edition)", gr.Textbox, {"visible": True}, section=section))

script_callbacks.on_ui_settings(on_ui_settings)

def download_single_item(model_data, api_key):
    headers = {"Authorization": f"Bearer {api_key}", "User-Agent": "Mozilla/5.0"}
    version = model_data['modelVersions'][0]
    
    clean_name = "".join([c for c in model_data['name'] if c.isalnum() or c in (' ', '_')]).rstrip()
    
    category = "General"
    if model_data.get('tags') and len(model_data['tags']) > 0:
        category = model_data['tags'][0].replace(' ', '_').replace('/', '_')
        
    target_dir = os.path.join(LORA_DIR, category)
    os.makedirs(target_dir, exist_ok=True)
    
    base_path = os.path.join(target_dir, clean_name)
    safetensors_path = f"{base_path}.safetensors"
    json_path = f"{base_path}.cm-info.json"
    preview_path = f"{base_path}.preview.png"

    if os.path.exists(safetensors_path):
        return f"[SKIP] {clean_name}"

    log = []
    try:
        info_url = f"https://civitai.com/api/v1/model-versions/{version['id']}"
        v_info = requests.get(info_url, headers=headers, timeout=10).json()
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(v_info, f, indent=4)
        log.append(f"[+] JSON: {clean_name}")

        if version.get('images') and len(version['images']) > 0:
            img_url = version['images'][0]['url']
            img_r = requests.get(img_url, timeout=10)
            with open(preview_path, 'wb') as f:
                f.write(img_r.content)
            log.append(f"[+] Preview: {clean_name}")

        dl_url = f"https://civitai.com/api/download/models/{version['id']}"
        r = requests.get(dl_url + f"?token={api_key}", stream=True, timeout=600)
        
        if r.status_code == 200:
            with open(safetensors_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk: f.write(chunk)
            log.append(f"[OK] MODELO: {clean_name}")
        else:
            log.append(f"[ERR] Falló descarga: {clean_name} (Code: {r.status_code})")
    except Exception as e:
        log.append(f"[CRIT] Error en {clean_name}: {str(e)}")
        
    return "\n".join(log)

def start_sync(query, limit, network_profile):
    api_key = shared.opts.data.get("civitai_api_key", "")
    if not api_key: return "❌ Error: Configura tu Civitai API Key en 'Settings' -> 'CivitaiFlow Manager'."
    if not query: return "⚠️ Ingresa un Tag de búsqueda."

    if "10 Mbps" in network_profile: active_threads = 1
    elif "100 Mbps" in network_profile: active_threads = 3
    else: active_threads = 8

    headers = {"Authorization": f"Bearer {api_key}", "User-Agent": "Mozilla/5.0"}
    api_url = f"https://civitai.com/api/v1/models?query={query.replace(' ', '+')}&limit={int(limit)}&types=LORA&sort=Highest+Rated"
    
    try:
        response = requests.get(api_url, headers=headers, timeout=30)
        models_data = response.json().get('items', [])
        if not models_data: return f"❌ No se encontraron LoRAs con '{query}'."

        final_log = [f"🚀 Iniciando QoS: {network_profile} ({active_threads} hilos) para {len(models_data)} modelos..."]
        
        with ThreadPoolExecutor(max_workers=active_threads) as executor:
            futures = [executor.submit(download_single_item, m, api_key) for m in models_data]
            for future in futures: final_log.append(future.result())
                
        return "\n".join(final_log)
    except Exception as e: return f"❌ Error: {str(e)}"

class Script(scripts.Script):
    def title(self): return "CivitaiFlow Manager"
    def show(self, is_img2img): return scripts.AlwaysVisible
    def ui(self, is_img2img):
        with gr.Accordion("Ronin Civitai Collector", open=False):
            gr.Markdown("### 📡 Adquisición Masiva de Activos (QoS Ready)")
            with gr.Row():
                query = gr.Textbox(label="Tag de búsqueda", placeholder="ej: Zenless Zone Zero")
                limit = gr.Slider(minimum=1, maximum=100, step=1, label="Límite", value=20)
                network_profile = gr.Dropdown(choices=["10 Mbps (Lento/Seguro)", "100 Mbps (Balanceado)", "500+ Mbps (Agresivo/Ronin)"], value="100 Mbps (Balanceado)", label="Perfil de Red (QoS)")
            
            gr.HTML("<p style='font-size: 13px; color: #a8a8a8;'>🔑 <a href='https://civitai.com/user/account' target='_blank' style='color: #ff7c00; text-decoration: none;'>Haz clic aquí para generar tu API Key en Civitai</a> y pégala en la pestaña <b>Settings</b> de Forge.</p>")
            
            run_btn = gr.Button("Iniciar Sincronización", variant="primary")
            output = gr.Textbox(label="Log de Consola", lines=12)
            
            run_btn.click(fn=start_sync, inputs=[query, limit, network_profile], outputs=[output])
        return [query, limit, network_profile]
