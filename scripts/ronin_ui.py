import os
import requests
import json
import modules.scripts as scripts
import gradio as gr
from modules import paths, shared, script_callbacks
from concurrent.futures import ThreadPoolExecutor

LORA_DIR = os.path.join(paths.models_path, "Lora")

# --- 1. SETTINGS GLOBALES ---
def on_ui_settings():
    section = ('civitai_flow', "CivitaiFlow Manager")
    shared.opts.add_option("civitai_api_key", shared.OptionInfo("", "Civitai API Key (Ronin Edition)", gr.Textbox, {"visible": True}, section=section))

script_callbacks.on_ui_settings(on_ui_settings)

# --- 2. AUTOCOMPLETADO DE TAGS (LIVE SEARCH) ---
def get_tag_suggestions(query):
    if not query or len(query) < 3:
        return gr.update(choices=[])
    
    url = f"https://civitai.com/api/v1/tags?query={query.replace(' ', '+')}&limit=10"
    try:
        res = requests.get(url, timeout=5).json()
        tags = [item['name'] for item in res.get('items', [])]
        return gr.update(choices=tags)
    except:
        return gr.update(choices=[])

# --- 3. MOTOR DE DESCARGA (SYSADMIN CORE) ---
def download_single_item(model_data, api_key):
    headers = {"Authorization": f"Bearer {api_key}", "User-Agent": "Mozilla/5.0"}
    version = model_data['modelVersions'][0]
    
    clean_name = "".join([c for c in model_data['name'] if c.isalnum() or c in (' ', '_')]).rstrip()
    category = model_data['tags'][0].replace(' ', '_').replace('/', '_') if model_data.get('tags') else "General"
    
    target_dir = os.path.join(LORA_DIR, category)
    os.makedirs(target_dir, exist_ok=True)
    
    base_path = os.path.join(target_dir, clean_name)
    safetensors_path = f"{base_path}.safetensors"
    json_path = f"{base_path}.json" # Formato nativo A1111/Forge
    preview_path = f"{base_path}.preview.png"

    if os.path.exists(safetensors_path):
        return f"[SKIP] {clean_name} (Ya existe)"

    log = []
    try:
        # A. METADATOS COMPATIBLES CON FORGE (A1111 Format)
        trained_words = version.get('trainedWords', [])
        forge_metadata = {
            "description": model_data.get('description', ""),
            "sd version": version.get('baseModel', "Unknown"),
            "activation text": ", ".join(trained_words),
            "preferred weight": 1.0,
            "notes": f"Descargado por CivitaiFlow. Link: https://civitai.com/models/{model_data['id']}"
        }
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(forge_metadata, f, indent=4)
        log.append(f"[+] Metadata Fix: {clean_name}")

        # B. PREVIEW IMAGEN
        if version.get('images') and len(version['images']) > 0:
            img_url = version['images'][0]['url']
            img_r = requests.get(img_url, timeout=10)
            with open(preview_path, 'wb') as f: f.write(img_r.content)
            log.append(f"[+] Preview: {clean_name}")

        # C. MODELO SAFETENSORS
        dl_url = f"https://civitai.com/api/download/models/{version['id']}"
        r = requests.get(dl_url + f"?token={api_key}", stream=True, timeout=600)
        
        if r.status_code == 200:
            with open(safetensors_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk: f.write(chunk)
            log.append(f"[OK] LORA: {clean_name}")
        else:
            log.append(f"[ERR] Falló: {clean_name} (HTTP {r.status_code})")
    except Exception as e:
        log.append(f"[CRIT] Error: {str(e)}")
        
    return "\n".join(log)

def start_sync(query, limit, threads):
    api_key = shared.opts.data.get("civitai_api_key", "")
    if not api_key: return "❌ Error: Configura tu API Key en la pestaña 'Settings'."
    if not query: return "⚠️ Ingresa o selecciona un Tag válido."

    headers = {"Authorization": f"Bearer {api_key}", "User-Agent": "Mozilla/5.0"}
    api_url = f"https://civitai.com/api/v1/models?query={query.replace(' ', '+')}&limit={int(limit)}&types=LORA&sort=Highest+Rated"
    
    try:
        response = requests.get(api_url, headers=headers, timeout=30)
        models_data = response.json().get('items', [])
        if not models_data: return f"❌ No se encontraron LoRAs con '{query}'."

        final_log = [f"🚀 Iniciando ráfaga ({threads} Hilos) para {len(models_data)} modelos..."]
        
        with ThreadPoolExecutor(max_workers=int(threads)) as executor:
            futures = [executor.submit(download_single_item, m, api_key) for m in models_data]
            for future in futures: final_log.append(future.result())
                
        return "\n".join(final_log)
    except Exception as e: return f"❌ Error API: {str(e)}"

# --- 4. CREACIÓN DE LA PESTAÑA PRINCIPAL (TAB) ---
def on_ui_tabs():
    with gr.Blocks(analytics_enabled=False) as civitai_flow_tab:
        gr.Markdown("## 📡 CivitaiFlow: Gestor Masivo de Activos")
        gr.HTML("<p style='font-size: 13px; color: #a8a8a8;'>🔑 <a href='https://civitai.com/user/account' target='_blank' style='color: #ff7c00; text-decoration: none;'>Obtén tu API Key aquí</a> y pégala en <b>Settings -> CivitaiFlow Manager</b>.</p>")
        
        with gr.Row():
            with gr.Column(scale=1):
                # Search Bar con Autocomplete
                search_query = gr.Dropdown(label="Tag Search (Escribe para autocompletar)", choices=[], allow_custom_value=True, elem_id="cf_search")
                search_query.change(fn=get_tag_suggestions, inputs=search_query, outputs=search_query)
                
                # Sliders Claros y precisos
                limit_slider = gr.Slider(minimum=1, maximum=100, step=1, label="Cantidad máxima a descargar", value=5)
                threads_slider = gr.Slider(minimum=1, maximum=20, step=1, label="Hilos de Conexión (QoS: 1=Seguro, 20=Unlimited/Ronin)", value=5)
                
                run_btn = gr.Button("🔥 Iniciar Sincronización Masiva", variant="primary")
            
            with gr.Column(scale=2):
                output_log = gr.Textbox(label="Consola de Sincronización (Live Status)", lines=15)
                
        run_btn.click(fn=start_sync, inputs=[search_query, limit_slider, threads_slider], outputs=[output_log])
        
    return [(civitai_flow_tab, "CivitaiFlow", "civitai_flow_tab")]

script_callbacks.on_ui_tabs(on_ui_tabs)

# --- 5. LIMPIEZA: Ocultar de txt2img ---
class CivitaiFlowScript(scripts.Script):
    def title(self): return "CivitaiFlow Manager"
    def show(self, is_img2img): return False # Ya no aparecerá abajo escondido
