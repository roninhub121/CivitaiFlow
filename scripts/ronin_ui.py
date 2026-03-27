import os
import requests
import json
import modules.scripts as scripts
import gradio as gr
from modules import paths, shared, script_callbacks
from concurrent.futures import ThreadPoolExecutor

LORA_DIR = os.path.join(paths.models_path, "Lora")

# --- SETTINGS ---
def on_ui_settings():
    section = ('civitai_flow', "CivitaiFlow Manager")
    shared.opts.add_option("civitai_api_key", shared.OptionInfo("", "Civitai API Key (Ronin Edition)", gr.Textbox, {"visible": True}, section=section))
script_callbacks.on_ui_settings(on_ui_settings)

# --- FETCH DATA ---
def fetch_raw_data(query, limit):
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
        model_names = []
        
        for m in models:
            name = m['name']
            img_url = "https://placehold.co/400x600?text=No+Image"
            if m.get('modelVersions') and m['modelVersions'][0].get('images'):
                img_url = m['modelVersions'][0]['images'][0]['url']
            
            gallery_images.append((img_url, name))
            model_names.append(name)
            
        status = f"✅ Encontrados {len(models)} modelos. Marca las casillas en la lista de la izquierda."
        return gallery_images, gr.update(choices=model_names, value=[]), status, models
    except Exception as e:
        return [], gr.update(choices=[], value=[]), f"❌ Error API: {str(e)}", []

# --- DOWNLOAD ENGINE ---
def download_single_item(model_data, api_key):
    headers = {"Authorization": f"Bearer {api_key}", "User-Agent": "Mozilla/5.0"}
    version = model_data['modelVersions'][0]
    
    clean_name = "".join([c for c in model_data['name'] if c.isalnum() or c in (' ', '_')]).rstrip()
    category = model_data['tags'][0].replace(' ', '_').replace('/', '_') if model_data.get('tags') else "General"
    
    target_dir = os.path.join(LORA_DIR, category)
    os.makedirs(target_dir, exist_ok=True)
    
    base_path = os.path.join(target_dir, clean_name)
    safetensors_path = f"{base_path}.safetensors"
    info_path = f"{base_path}.civitai.info" # Fix de metadata requerido por Forge
    preview_path = f"{base_path}.preview.png"

    if os.path.exists(safetensors_path):
        return f"[SKIP] {clean_name} (Ya existe)"

    log = []
    try:
        v_url = f"https://civitai.com/api/v1/model-versions/{version['id']}"
        v_info = requests.get(v_url, headers=headers, timeout=10).json()
        with open(info_path, 'w', encoding='utf-8') as f:
            json.dump(v_info, f, indent=4)

        if version.get('images'):
            img_r = requests.get(version['images'][0]['url'], timeout=10)
            with open(preview_path, 'wb') as f: f.write(img_r.content)

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
    if not selected_names: return "⚠️ No has marcado ninguna casilla en el carrito."
    
    models_to_download = [m for m in hidden_models_data if m['name'] in selected_names]
    final_log = [f"🚀 Iniciando descarga paralela para {len(models_to_download)} modelos..."]
    
    with ThreadPoolExecutor(max_workers=int(threads)) as executor:
        futures = [executor.submit(download_single_item, m, api_key) for m in models_to_download]
        for future in futures: final_log.append(future.result())
            
    return "\n".join(final_log)

# --- UI TABS ---
def on_ui_tabs():
    with gr.Blocks(analytics_enabled=False) as civitai_flow_tab:
        gr.Markdown("## 📡 CivitaiFlow: Visual Asset Manager (Shopping Cart UI)")
        
        hidden_data = gr.State([])

        with gr.Row():
            # COLUMNA IZQUIERDA: Controles y Checkboxes (Carrito)
            with gr.Column(scale=1):
                gr.Markdown("### 1. Búsqueda")
                search_query = gr.Textbox(label="Búsqueda por Tag", placeholder="ej: Ahri")
                limit_slider = gr.Slider(minimum=1, maximum=30, step=1, label="Resultados a mostrar", value=12)
                search_btn = gr.Button("🔍 Buscar Previews", variant="secondary")
                
                gr.Markdown("---")
                gr.Markdown("### 2. Carrito de Descarga")
                gr.Markdown("<small>Mira la galería a la derecha y marca aquí los que quieras bajar.</small>")
                selected_models_checkboxes = gr.CheckboxGroup(label="Modelos Seleccionados", choices=[], elem_id="cf_checkboxes")
                
                threads_slider = gr.Slider(minimum=1, maximum=20, step=1, label="Hilos de Conexión (QoS)", value=5)
                download_btn = gr.Button("⬇️ Descargar Marcados", variant="primary", size="lg")

            # COLUMNA DERECHA: Catálogo Visual
            with gr.Column(scale=2):
                status_log = gr.Textbox(label="Status y Consola (Live Log)", lines=4)
                
                gr.Markdown("### 3. Catálogo Visual (Referencia)")
                gallery_size_slider = gr.Slider(minimum=2, maximum=8, step=1, label="Tamaño de Columnas", value=4)
                gallery = gr.Gallery(label="Previsualización", show_label=False, columns=[4], object_fit="contain", height="auto")

        # EVENTOS
        search_btn.click(fn=fetch_raw_data, inputs=[search_query, limit_slider], outputs=[gallery, selected_models_checkboxes, status_log, hidden_data])
        search_query.submit(fn=fetch_raw_data, inputs=[search_query, limit_slider], outputs=[gallery, selected_models_checkboxes, status_log, hidden_data])
        
        gallery_size_slider.change(fn=lambda x: gr.update(columns=int(x)), inputs=gallery_size_slider, outputs=gallery)
        
        download_btn.click(fn=start_download, inputs=[selected_models_checkboxes, hidden_data, threads_slider], outputs=status_log)
        
    return [(civitai_flow_tab, "CivitaiFlow", "civitai_flow_tab")]

script_callbacks.on_ui_tabs(on_ui_tabs)
