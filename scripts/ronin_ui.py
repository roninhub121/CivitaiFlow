import os
import requests
import json
import modules.scripts as scripts
import gradio as gr
from modules import paths, shared, script_callbacks
from concurrent.futures import ThreadPoolExecutor

LORA_DIR = os.path.join(paths.models_path, "Lora")

# --- SETTINGS GLOBALES ---
def on_ui_settings():
    section = ('civitai_flow', "CivitaiFlow Manager")
    shared.opts.add_option("civitai_api_key", shared.OptionInfo("", "Civitai API Key (Ronin Edition)", gr.Textbox, {"visible": True}, section=section))
script_callbacks.on_ui_settings(on_ui_settings)

# --- FASE 1: BUSCADOR Y GALERÍA VISUAL ---
def fetch_previews(query, limit):
    api_key = shared.opts.data.get("civitai_api_key", "")
    if not api_key: return [], gr.update(choices=[], value=[]), "❌ Configura tu API Key en Settings", []
    if not query: return [], gr.update(choices=[], value=[]), "⚠️ Ingresa un tag válido", []

    headers = {"Authorization": f"Bearer {api_key}", "User-Agent": "Mozilla/5.0"}
    api_url = f"https://civitai.com/api/v1/models?query={query.replace(' ', '+')}&limit={int(limit)}&types=LORA&sort=Highest+Rated"
    
    try:
        res = requests.get(api_url, headers=headers, timeout=15)
        models = res.json().get('items', [])
        
        if not models:
            return [], gr.update(choices=[], value=[]), "❌ No se encontraron resultados.", []

        gallery_images = []
        checkbox_choices = []
        
        for m in models:
            name = m['name']
            # Obtener la URL de la primera imagen
            img_url = "https://placehold.co/400x600?text=No+Image"
            if m.get('modelVersions') and m['modelVersions'][0].get('images'):
                img_url = m['modelVersions'][0]['images'][0]['url']
            
            gallery_images.append((img_url, name))
            checkbox_choices.append(name)
            
        return gallery_images, gr.update(choices=checkbox_choices, value=checkbox_choices), f"✅ Se encontraron {len(models)} modelos. Desmarca los que no quieras.", models
    except Exception as e:
        return [], gr.update(choices=[], value=[]), f"❌ Error: {str(e)}", []

# --- FASE 2: DESCARGA DEL CÓDIGO SELECCIONADO ---
def download_single_item(model_data, api_key):
    headers = {"Authorization": f"Bearer {api_key}", "User-Agent": "Mozilla/5.0"}
    version = model_data['modelVersions'][0]
    
    clean_name = "".join([c for c in model_data['name'] if c.isalnum() or c in (' ', '_')]).rstrip()
    category = model_data['tags'][0].replace(' ', '_').replace('/', '_') if model_data.get('tags') else "General"
    
    target_dir = os.path.join(LORA_DIR, category)
    os.makedirs(target_dir, exist_ok=True)
    
    base_path = os.path.join(target_dir, clean_name)
    safetensors_path = f"{base_path}.safetensors"
    info_path = f"{base_path}.civitai.info" # <--- EL FIX DE METADATA PARA FORGE
    preview_path = f"{base_path}.preview.png"

    if os.path.exists(safetensors_path):
        return f"[SKIP] {clean_name} (Ya existe)"

    log = []
    try:
        # A. METADATA: Bajar el raw JSON de la versión exacta para que Forge lea las Activation Words
        v_url = f"https://civitai.com/api/v1/model-versions/{version['id']}"
        v_info = requests.get(v_url, headers=headers, timeout=10).json()
        with open(info_path, 'w', encoding='utf-8') as f:
            json.dump(v_info, f, indent=4)
        log.append(f"[+] Info Fix: {clean_name}")

        # B. PREVIEW
        if version.get('images'):
            img_r = requests.get(version['images'][0]['url'], timeout=10)
            with open(preview_path, 'wb') as f: f.write(img_r.content)

        # C. MODELO
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
        log.append(f"[CRIT] Error en {clean_name}: {str(e)}")
        
    return "\n".join(log)

def start_download(selected_names, hidden_models_data, threads):
    api_key = shared.opts.data.get("civitai_api_key", "")
    if not selected_names: return "⚠️ No has seleccionado ningún modelo."
    
    # Filtrar solo los modelos que el usuario dejó marcados
    models_to_download = [m for m in hidden_models_data if m['name'] in selected_names]
    
    final_log = [f"🚀 Iniciando descarga de {len(models_to_download)} modelos seleccionados ({threads} Hilos)..."]
    
    with ThreadPoolExecutor(max_workers=int(threads)) as executor:
        futures = [executor.submit(download_single_item, m, api_key) for m in models_to_download]
        for future in futures: final_log.append(future.result())
            
    return "\n".join(final_log)

# --- INTERFAZ GRÁFICA ---
def on_ui_tabs():
    with gr.Blocks() as civitai_flow_tab:
        gr.Markdown("## 📡 CivitaiFlow: Visual Asset Manager")
        gr.HTML("<p style='font-size: 13px; color: gray;'>Configura tu API Key en <b>Settings -> CivitaiFlow Manager</b>.</p>")
        
        # Estado oculto para guardar la data cruda de la API entre clics
        hidden_data = gr.State([])
        
        with gr.Row():
            with gr.Column(scale=1):
                search_query = gr.Textbox(label="1. Buscar Tag (ej: Ahri, Cyberpunk)", placeholder="Escribe y presiona Enter o Buscar...")
                limit_slider = gr.Slider(minimum=1, maximum=20, step=1, label="Resultados a mostrar", value=10)
                search_btn = gr.Button("🔍 Buscar y Cargar Previews", variant="secondary")
                
            with gr.Column(scale=2):
                status_log = gr.Textbox(label="Status", lines=3)
                
        gr.Markdown("### 2. Galería de Previsualización")
        gallery = gr.Gallery(label="Modelos Encontrados", show_label=False, elem_id="gallery", columns=[4], rows=[2], object_fit="contain", height="auto")
        
        gr.Markdown("### 3. Selección y Descarga")
        with gr.Row():
            with gr.Column(scale=2):
                selected_models = gr.CheckboxGroup(label="Modelos listos para descargar (Desmarca los que no quieras)", choices=[])
            with gr.Column(scale=1):
                threads_slider = gr.Slider(minimum=1, maximum=20, step=1, label="Hilos (1=Lento, 20=Unlimited)", value=5)
                download_btn = gr.Button("⬇️ Descargar Selección", variant="primary", size="lg")
                
        # Conexión de botones
        search_btn.click(fn=fetch_previews, inputs=[search_query, limit_slider], outputs=[gallery, selected_models, status_log, hidden_data])
        search_query.submit(fn=fetch_previews, inputs=[search_query, limit_slider], outputs=[gallery, selected_models, status_log, hidden_data])
        
        download_btn.click(fn=start_download, inputs=[selected_models, hidden_data, threads_slider], outputs=[status_log])
        
    return [(civitai_flow_tab, "CivitaiFlow", "civitai_flow_tab")]

script_callbacks.on_ui_tabs(on_ui_tabs)
