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

# --- 2. FASE BUSCADOR (GET RAW DATA) ---
def fetch_raw_data(query, limit):
    api_key = shared.opts.data.get("civitai_api_key", "")
    if not api_key or len(api_key) < 5: return [], "❌ Configura tu API Key en Settings", []
    if not query: return [], "⚠️ Ingresa un tag válido", []

    headers = {"Authorization": f"Bearer {api_key}", "User-Agent": "Mozilla/5.0"}
    api_url = f"https://civitai.com/api/v1/models?query={query.replace(' ', '+')}&limit={int(limit)}&types=LORA&sort=Highest+Rated"
    
    try:
        res = requests.get(api_url, headers=headers, timeout=15)
        models = res.json().get('items', [])
        
        if not models:
            return [], "❌ No se encontraron resultados.", []

        gallery_images = []
        for m in models:
            name = m['name']
            img_url = "https://placehold.co/400x600?text=No+Image"
            if m.get('modelVersions') and m['modelVersions'][0].get('images'):
                img_url = m['modelVersions'][0]['images'][0]['url']
            gallery_images.append((img_url, name))
            
        status = f"✅ Se encontraron {len(models)} modelos. Haz clic sobre las imágenes para marcar/desmarcar."
        return gallery_images, status, models
    except Exception as e:
        return [], f"❌ Error API: {str(e)}", []

# --- 3. LÓGICA DE SELECCIÓN VISUAL (EVENT HANDLER) ---
def handle_gallery_selection(evt: gr.SelectData, selected_indices, hidden_models_data):
    if not hidden_models_data:
        return gr.update(value=[]), "❌ No data to select from."

    # Gradio selection event returns the index of the clicked item
    current_index = evt.index
    
    # Toggle logic: if already selected, remove. if not, add.
    if current_index in selected_indices:
        selected_indices.remove(current_index)
    else:
        selected_indices.append(current_index)

    # Convert indices back to names for the status log
    selected_names = [hidden_models_data[idx]['name'] for idx in selected_indices]

    log_update = f"🛠️ Modelos seleccionados ({len(selected_names)}): {', '.join(selected_names)}.\nAhora presiona 'Descargar Selección'."
    return selected_indices, log_update # Update state and status log

# --- 4. MOTOR DE DESCARGA (SYSADMIN CORE + METADATA FIX) ---
def download_single_item(model_data, api_key):
    headers = {"Authorization": f"Bearer {api_key}", "User-Agent": "Mozilla/5.0"}
    version = model_data['modelVersions'][0]
    
    clean_name = "".join([c for c in model_data['name'] if c.isalnum() or c in (' ', '_')]).rstrip()
    category = model_data['tags'][0].replace(' ', '_').replace('/', '_') if model_data.get('tags') else "General"
    
    target_dir = os.path.join(LORA_DIR, category)
    os.makedirs(target_dir, exist_ok=True)
    
    base_path = os.path.join(target_dir, clean_name)
    safetensors_path = f"{base_path}.safetensors"
    # Forge y A1111 necesitan .civitai.info para leer los Activation Words
    info_path = f"{base_path}.civitai.info" # <--- EL FIX DE METADATA DEFINITIVO
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

        # B. PREVIEW IMAGEN
        if version.get('images') and len(version['images']) > 0:
            img_r = requests.get(version['images'][0]['url'], timeout=10)
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
        log.append(f"[CRIT] Error en {clean_name}: {str(e)}")
        
    return "\n".join(log)

def start_download(selected_indices, hidden_models_data, threads):
    api_key = shared.opts.data.get("civitai_api_key", "")
    if not selected_indices: return "⚠️ No has seleccionado ningún modelo."
    if not hidden_models_data: return "⚠️ No data found. Please search again."
    
    # Filtrar solo los modelos que el usuario marcó visualmente
    models_to_download = [hidden_models_data[idx] for idx in selected_indices]
    
    final_log = [f"🚀 Iniciando ráfaga paralela ({threads} Hilos) para {len(models_to_download)} modelos seleccionados..."]
    
    with ThreadPoolExecutor(max_workers=int(threads)) as executor:
        futures = [executor.submit(download_single_item, m, api_key) for m in models_to_download]
        for future in futures: final_log.append(future.result())
            
    return "\n".join(final_log)

# --- 5. CREACIÓN DE LA PESTAÑA PRINCIPAL (TAB) - ARQUITECTURA 2 COLUMNAS ---
def on_ui_tabs():
    with gr.Blocks(analytics_enabled=False) as civitai_flow_tab:
        gr.Markdown("## 📡 CivitaiFlow: Visual Asset Manager v3.0 (Ronin Edition)")
        gr.HTML("<p style='font-size: 13px; color: gray;'>🔑 Configura tu API Key en <b>Settings -> CivitaiFlow Manager</b>.</p>")

        # Estados ocultos para guardar la data cruda y la selección visual
        hidden_data = gr.State([])
        selected_indices = gr.State([]) # To store indexes from visual selection

        with gr.Row():
            # COLUMNA IZQUIERDA (scale=1): Menus de Control
            with gr.Column(scale=1):
                gr.Markdown("### 1. Búsqueda y QoS")
                search_query = gr.Textbox(label="Búsqueda por Tag (ej: Ahri, Cyberpunk)", placeholder="Escribe y presiona Enter o Buscar...", elem_id="cf_search")
                limit_slider = gr.Slider(minimum=1, maximum=20, step=1, label="Resultados a mostrar", value=10, elem_id="cf_limit")
                threads_slider = gr.Slider(minimum=1, maximum=20, step=1, label="Hilos (1=Seguro, 20=Unlimited)", value=5, elem_id="cf_threads")
                search_btn = gr.Button("🔍 Buscar y Cargar Previews", variant="secondary", elem_id="cf_search_btn")

                gr.Markdown("---")
                gr.Markdown("### 2. Controles de Galería y Acción")
                
                # NEW: Size Slider (Columnas)
                gallery_size_slider = gr.Slider(minimum=2, maximum=8, step=1, label="Tamaño de Previsualización (Columnas)", value=4, elem_id="cf_size_slider")

                # Download Button
                download_btn = gr.Button("⬇️ Descargar Selección Visual", variant="primary", size="lg", elem_id="cf_download_btn")

            # COLUMNA DERECHA (scale=2): Previsualización y Logs
            with gr.Column(scale=2):
                status_log = gr.Textbox(label="Status y Consola (Live Log)", lines=5, elem_id="cf_status")

                gr.Markdown("### 3. Galería de Selección (Haz clic para marcar/desmarcar)")
                # selectable=True and type="image" is the key for visual selection
                gallery = gr.Gallery(label="Modelos Encontrados", show_label=False, elem_id="cf_gallery", type="image", selectable=True, columns=[4], object_fit="contain", height="auto")

        # --- CONEXIÓN DE EVENTOS ---
        # Search / Submit
        search_btn.click(fn=fetch_raw_data, inputs=[search_query, limit_slider], outputs=[gallery, status_log, hidden_data])
        search_query.submit(fn=fetch_raw_data, inputs=[search_query, limit_slider], outputs=[gallery, status_log, hidden_data])

        # Resize Gallery (Zoom) - Update columns property dynamically
        gallery_size_slider.change(fn=lambda x: gr.update(columns=int(x)), inputs=gallery_size_slider, outputs=gallery)

        # Visual Selection in Gallery: Trigger handle_gallery_selection
        # selected_indices, status_log = handle_gallery_selection(select_data, selected_indices, hidden_data)
        gallery.select(fn=handle_gallery_selection, inputs=[selected_indices, hidden_data], outputs=[selected_indices, status_log])

        # Download: Uses selected_indices and hidden_data
        download_btn.click(fn=start_download, inputs=[selected_indices, hidden_data, threads_slider], outputs=status_log)
        
    return [(civitai_flow_tab, "CivitaiFlow", "civitai_flow_tab")]

script_callbacks.on_ui_tabs(on_ui_tabs)
