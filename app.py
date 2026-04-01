"""
app.py
------
Main AAC application entry point.
Refactored to use data_manager.py (YAML/Folder) storage and Admin Mode.
Enhanced with Image Upload/Paste support and Recycle Bin.
"""


from nicegui import ui, app
from data_manager import (
    get_categories,
    get_items,
    create_category,
    create_item,
    update_item,
    log_usage,
    delete_item,
    soft_delete_item,
    restore_item,
    permanent_delete_item,
    get_trash_items,
    empty_trash,
    delete_category,
    rename_category,
    toggle_category_visibility,
    set_category_color,
    toggle_item_visibility,
    move_category_up,
    move_category_down,
    read_config,
    write_config,
    search_opensymbols,
    download_image_from_url,
    update_secret,
    test_secret,
    DATA_DIR
)
import os
import base64
import random
import yaml
import asyncio

# Serve the data directory for images
app.add_static_files('/data', str(DATA_DIR))

print('test')

def setup_header():
    # Disable pinch-to-zoom on mobile devices (Meta tag + JS listeners for iOS 10+)
    ui.add_head_html('<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">')
    ui.add_head_html('''
<script>
    // Aggressively prevent pinch-zoom events (iOS ignores user-scalable=no)
    document.addEventListener('gesturestart', function(e) { e.preventDefault(); });
    document.addEventListener('gesturechange', function(e) { e.preventDefault(); });
    document.addEventListener('gestureend', function(e) { e.preventDefault(); });
</script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Sortable/1.15.0/Sortable.min.js"></script>
''')

    # Add iOS-specific CSS for touch interactions
    ui.add_head_html('''
<style>
    /* Enable touch interactions on iOS */
    .item-card {
        -webkit-tap-highlight-color: rgba(59, 130, 246, 0.3);
        -webkit-touch-callout: none;
        -webkit-user-select: none;
        user-select: none;
        cursor: pointer;
        touch-action: manipulation;
    }
    
    /* Active state for touch feedback */
    .item-card:active {
        transform: scale(0.95);
        transition: transform 0.1s ease;
    }
    
    /* Ensure child elements don't block touch events */
    .item-card * {
        pointer-events: none;
    }
    
    /* Re-enable pointer events for admin buttons */
    .item-card .admin-controls,
    .item-card .admin-controls * {
        pointer-events: auto;
    }

    /* Sortable ghost class */
    .sortable-ghost {
        opacity: 0.4;
        background-color: #f3f4f6;
    }

</style>
''')

    # Initialize speech synthesis for iOS (requires user interaction to unlock)
    ui.add_head_html('''
<script>
    // iOS Safari requires an initial user interaction to enable speech synthesis
    // This script initializes it on first touch/click
    (function() {
        let initialized = false;
        
        function initSpeech() {
            if (!initialized && window.speechSynthesis) {
                // Create a silent utterance to "unlock" speech synthesis on iOS
                const utterance = new SpeechSynthesisUtterance('');
                utterance.volume = 0;
                speechSynthesis.speak(utterance);
                initialized = true;
                
                // Remove listeners after initialization
                document.removeEventListener('touchstart', initSpeech);
                document.removeEventListener('click', initSpeech);
            }
        }
        
        // Listen for first user interaction
        document.addEventListener('touchstart', initSpeech, { once: true });
        document.addEventListener('click', initSpeech, { once: true });
    })();
</script>
''')

# Global state
is_admin_mode = {"value": False}
is_sentence_mode = {"value": False}
sentence_queue = []
main_column = None
sentence_bar_container = None
grid_container = None
grid_item_size = {"value": 128}

# Remove default padding and gap - moved to index_page
# ui.query('nicegui-content').classes('gap-0 p-0')

# --------------------------------------------------
# UI Component: Item Button
# --------------------------------------------------

def make_item_button(item, is_trash=False, size_px=128):
    """Create clickable item button with image support."""

    is_visible = item.get("visible", True)
    # Added flex flex-col so flex-grow works, and item-card class for iOS touch support
    # Removed w-32 h-40 to allow dynamic sizing via style
    base_classes = "item-card m-0 p-0 gap-0 flex flex-col items-center hover:scale-105 transition-transform cursor-pointer shadow-md relative"
    if not is_visible:
        base_classes += " opacity-50 grayscale border-2 border-dashed"
        
    # Calculate height based on 1.25 aspect ratio (approx w-32 h-40)
    height_px = size_px * 1.25
    
    card = ui.card().classes(base_classes).style(f"width: {size_px}px; height: {height_px}px")
    
    if is_trash:
        card.classes(remove="hover:scale-105 cursor-pointer item-card") # Disable hover/click effects
    else:
        # INTERACTION LOGIC
        if is_admin_mode["value"]:
            # Admin Mode: Simple server-side click to open dialog
            card.on("click", lambda: open_edit_dialog(item))
            # Touch start handled by generic CSS/JS, no specific action needed
        else:
            # User Mode: Standard or Sentence Mode
            
            # Prepare safe text for JS
            text = (item.get("tts_text") or item["label"]).replace('"', '\\"').replace("'", "\\'")
            
            if is_sentence_mode["value"]:
                 # Sentence Mode: Add to queue
                 def add_to_queue():
                     sentence_queue.append(item)
                     # ui.notify(f"Added '{item['label']}'")
                     refresh_sentence_bar() # Update ONLY sentence bar, not whole grid
                 
                 # Queue mode: Add to sentence bar only, do not speak immediately
                 card.on("click", add_to_queue)
            
            else:
                # Standard Mode: Speak immediately
                
                # This JS runs IMMEDIATELY on click/tap, preserving the user gesture
                js_handler = f'''
                    (e) => {{
                        // iOS Fix: Explicitly cancel and resume to ensure audio context is ready
                        window.speechSynthesis.cancel();
                        window.speechSynthesis.resume();
                        
                        const utterance = new SpeechSynthesisUtterance("{text}");
                        utterance.rate = 1.0;
                        utterance.pitch = 1.0;
                        utterance.volume = 1.0;
                        
                        window.speechSynthesis.speak(utterance);
                        
                        // Return true to allow the event to propagate to the server (for logging)
                        return true; 
                    }}
                '''
                
                # Bind click with JS handler for immediate feedback
                card.on("click", lambda: log_usage(item["id"]), js_handler=js_handler)
                
                # Aggressive iOS wakeup on touchstart
                card.on("touchstart", js_handler='(e) => { window.speechSynthesis.resume(); return true; }', throttle=0.0)

    with card:
        # Image area
        img_src = None
        if item["image_path"]:
            if item["image_path"].startswith("http"):
                img_src = item["image_path"]
            elif os.path.isabs(item["image_path"]):
                try:
                    rel_path = os.path.relpath(item["image_path"], str(DATA_DIR))
                    # Add cache-busting timestamp to force browser refresh
                    import time
                    timestamp = int(time.time())
                    img_src = f"/data/{rel_path}?t={timestamp}"
                except ValueError:
                    img_src = None

        if img_src:
            ui.image(img_src).classes("w-full h-0 min-h-0 flex-grow object-cover rounded-t")
        else:
            # Placeholder icon
            with ui.column().classes("w-full h-0 min-h-0 flex-grow bg-gray-100 items-center justify-center rounded-t"):
                ui.icon("image_not_supported").classes("text-3xl text-gray-300")

        # Label area
        ui.label(item["label"]).classes("text-sm font-bold text-center leading-tight w-full overflow-hidden text-ellipsis px-1 pb-1")
        
        # Admin indicator & Controls
        if is_admin_mode["value"] and not is_trash:
             with ui.column().classes("admin-controls absolute top-1 right-1 gap-1 z-20"):
                # Visibility Toggle
                def toggle_vis(e, i_id=item["id"], c_id=item["cat_id"]):
                    e.stop_propagation()
                    toggle_item_visibility(c_id, i_id)
                    refresh_grid() # Only refresh grid

                vis_icon = "visibility" if is_visible else "visibility_off"
                # Removed opacity, increased z-index (z-20 parent), ensured white bg
                ui.button(icon=vis_icon, on_click=toggle_vis).props(f"flat dense round size=xs color={'black' if is_visible else 'red'}").classes("bg-white shadow ring-1 ring-gray-200")

                # Edit Indicator
                ui.icon("edit").classes("text-xs text-blue-500 bg-white rounded-full p-1 shadow")
        
        # Trash actions
        if is_trash:
             with ui.row().classes("w-full justify-between items-center px-1"):
                 ui.button(icon="restore_from_trash", on_click=lambda: restore_from_trash(item)).props("flat dense data-title='Restore'").classes("text-green-500")
                 ui.button(icon="delete_forever", on_click=lambda: delete_forever(item)).props("flat dense data-title='Delete Forever'").classes("text-red-500")


# --------------------------------------------------
# Dialogs
# --------------------------------------------------

async def handle_file_upload(e, file_container):
    """Async handler for file uploads."""
    data = await e.file.read()
    handle_image_data(data, file_container)

def handle_image_data(content, file_container):
    """Helper to store base64/bytes content until save."""
    if isinstance(content, str) and content.startswith("data:"):
        # Decode base64 data URL
        header, encoded = content.split(",", 1)
        data = base64.b64decode(encoded)
        file_container["data"] = data
        ui.notify("Image pasted!")
    elif isinstance(content, bytes):
        file_container["data"] = content
        ui.notify(f"Image uploaded! Size: {len(content)} bytes")
    else:
        ui.notify("Error: Unsupported content type", color="red")

# --------------------------------------------------
# Symbol Search Dialog
# --------------------------------------------------

def open_symbol_search_dialog(on_select):
    """
    Opens a dialog to search for symbols.
    on_select: callback function(image_url, label)
    """
    with ui.dialog() as dialog, ui.card().classes("w-full max-w-4xl h-3/4"):
        ui.label("Search OpenSymbols").classes("text-xl font-bold")
        
        with ui.row().classes("w-full gap-2"):
            search_input = ui.input("Search query").classes("flex-grow")
            
            # Results container
            results_container = ui.row().classes("w-full flex-wrap gap-2 overflow-y-auto p-2 border bg-gray-50 rounded h-full")

            async def do_search():
                query = search_input.value
                if not query:
                    ui.notify("Please enter a search term.")
                    return
                
                results_container.clear()
                with results_container:
                     ui.spinner("dots").classes("mx-auto")
                
                # Run sync search in executor to avoid blocking UI
                # nicegui's run.io_bound is perfect here
                async def run_search():
                    try:
                        loop = asyncio.get_running_loop()
                        results = await loop.run_in_executor(None, search_opensymbols, query)
                        results_container.clear()
                        
                        if not results:
                            with results_container:
                                 ui.label("No results found.").classes("text-gray-500 italic")
                            return

                        with results_container:
                            for item in results:
                                # Only show items with valid keys/images
                                if "image_url" not in item:
                                    continue
                                    
                                img_url = item["image_url"]
                                label = item.get("name", "Unknown")
                                
                                def make_select_handler(url, lbl):
                                    return lambda: [on_select(url, lbl), dialog.close()]

                                with ui.card().classes("w-32 h-40 p-1 flex flex-col items-center hover:bg-blue-50 cursor-pointer").on("click", make_select_handler(img_url, label)):
                                    ui.image(img_url).classes("w-full h-24 object-contain")
                                    ui.label(label).classes("text-xs text-center overflow-hidden w-full text-ellipsis mt-1")
                    except Exception as e:
                        results_container.clear()
                        with results_container:
                            ui.label(f"Search failed: {str(e)}").classes("text-red-500 font-bold")
                            ui.label("Check logs or config.").classes("text-gray-500 text-xs")
                
                # Run async wrapper
                await run_search()

            ui.button("Search", on_click=do_search, icon="search")
            search_input.on('keydown.enter', do_search)

        with ui.row().classes("w-full justify-end mt-4"):
             ui.button("Close", on_click=dialog.close).props("flat")

    dialog.open()


def open_edit_dialog(item):
    """Edit existing item."""
    # Get categories for dropdown
    categories = get_categories()
    
    with ui.dialog() as dialog, ui.card().classes("w-96"):
        ui.label(f"Edit: {item['label']}").classes("text-lg font-bold")
        
        # Category Selector
        cat_options = {c["id"]: c["name"] for c in categories}
        cat_select = ui.select(cat_options, label="Category", value=item["cat_id"]).classes("w-full mb-2")
        
        # Form Fields
        name_input = ui.input("Label", value=item["label"]).classes("w-full")
        tts_input = ui.input("TTS Text (Optional)", value=item.get("tts_text", "")).classes("w-full")
        
        # Visibility Toggle
        visible_switch = ui.switch("Visible", value=item.get("visible", True)).classes("w-full mt-2")

        ui.button("Search OpenSymbols", icon="search", on_click=lambda: open_symbol_search_dialog(handle_symbol_select)).props("flat dense color=blue").classes("w-full mt-1")

        ui.label("Update Image:").classes("text-sm font-bold mt-2")
        


        uploaded_file = {"data": None}
        
        # Fallback Upload
        ui.upload(on_upload=lambda e: handle_file_upload(e, uploaded_file), auto_upload=True).props("accept=image/* flat dense").classes("w-full mt-1")

        # Symbol Search Integration
        def handle_symbol_select(url, label):
             ui.notify(f"Selected: {label}")
             # Download immediately
             # Note: This blocks main thread briefly, but usually fast. 
             # Could be async but keep simple for now.
             data = download_image_from_url(url)
             if data:
                 uploaded_file["data"] = data
                 ui.notify("Image downloaded!")
             else:
                 ui.notify("Failed to download image.", color="red")

        ui.button("Search OpenSymbols", icon="search", on_click=lambda: open_symbol_search_dialog(handle_symbol_select)).props("flat dense color=blue").classes("w-full mt-1")

        def save():
            ui.notify("Updating...")
            update_item(
                item["cat_id"], 
                item["id"], 
                new_label=name_input.value,
                new_tts_text=tts_input.value,
                new_image_file=uploaded_file["data"],
                new_category_id=cat_select.value,
                new_visible=visible_switch.value
            )
            dialog.close()
            refresh_grid()

        def delete():
            with ui.dialog() as confirm_dialog, ui.card():
                ui.label("Move to Recycle Bin?").classes("text-lg font-bold")
                with ui.row().classes("w-full justify-end mt-4"):
                    ui.button("Cancel", on_click=confirm_dialog.close).props("flat")
                    def do_delete():
                        ui.notify("Moved to Trash")
                        soft_delete_item(item["cat_id"], item["id"])
                        dialog.close()
                        confirm_dialog.close()
                        refresh_grid()
                    ui.button("Delete", color="red", on_click=do_delete)
            confirm_dialog.open()

        with ui.row().classes("w-full justify-between mt-4"):
            ui.button("Delete", on_click=delete, color="red").props("flat")
            ui.button("Save", on_click=save)

    dialog.open()

def open_add_item_dialog(category_id=None):
    """Add new item. If category_id is None, user selects it."""
    
    # Get categories for dropdown
    categories = get_categories()
    if not categories:
        ui.notify("Create a category first!", color="warning")
        return

    with ui.dialog() as dialog, ui.card().classes("w-96"):
        ui.label("Add New Item").classes("text-lg font-bold")
        
        # Category Selector
        cat_options = {c["id"]: c["name"] for c in categories}
        cat_select = ui.select(cat_options, label="Category").classes("w-full")
        
        # Pre-select if provided, else default to first
        if category_id and category_id in cat_options:
            cat_select.value = category_id
        elif categories:
             cat_select.value = categories[0]["id"]
        
        name_input = ui.input("Label").classes("w-full")
        tts_input = ui.input("TTS Text (Optional)").classes("w-full")
        
        ui.label("Image:").classes("text-sm font-bold mt-2")
        ui.button("Search OpenSymbols", icon="search", on_click=lambda: open_symbol_search_dialog(handle_symbol_select)).props("flat dense color=blue").classes("w-full mt-1")

        uploaded_file = {"data": None, "url": None}

        # Image preview (hidden until an image is selected)
        image_preview = ui.image("").classes("w-32 h-32 object-contain mx-auto mt-1")
        image_preview.set_visibility(False)

        ui.upload(on_upload=lambda e: handle_file_upload(e, uploaded_file), auto_upload=True).props("accept=image/* flat dense").classes("w-full mt-1")

        # Symbol Search Integration
        def handle_symbol_select(url, label):
             # Auto-fill label if empty
             if not name_input.value:
                 name_input.value = label

             # Always store the URL as a fallback (covers SVG and other PIL-unsupported formats)
             uploaded_file["url"] = url

             # Try to download for local storage
             data = download_image_from_url(url)
             if data:
                 uploaded_file["data"] = data

             # Show preview using the original URL regardless of download outcome
             image_preview.set_source(url)
             image_preview.set_visibility(True)
             ui.notify("Image selected!")


        def save():
            if not cat_select.value:
                ui.notify("Please select a category.")
                return

            if name_input.value:
                ui.notify("Creating...")
                create_item(
                    cat_select.value,
                    name_input.value,
                    image_file=uploaded_file["data"],
                    image_url=uploaded_file["url"],
                    tts_text=tts_input.value
                )
                dialog.close()
                refresh_grid()

        ui.button("Create", on_click=save).classes("w-full mt-4")

    dialog.open()

def open_add_category_dialog():
    with ui.dialog() as dialog, ui.card().classes("w-96"):
        ui.label("New Category").classes("text-lg font-bold")
        name_input = ui.input("Name").classes("w-full")
        
        def save():
            if name_input.value:
                create_category(name_input.value)
                refresh_grid()
                dialog.close()
        
        ui.button("Create", on_click=save).classes("w-full mt-4")
    dialog.open()

# --------------------------------------------------
# Recycle Bin UI
# --------------------------------------------------

trash_dialog = None

def open_recycle_bin():
    global trash_dialog
    trash_items = get_trash_items()
    
    with ui.dialog() as dialog, ui.card().classes("w-full max-w-4xl h-3/4"):
        trash_dialog = dialog
        with ui.row().classes("w-full justify-between items-center mb-4"):
            ui.label("Recycle Bin").classes("text-2xl font-bold")
            ui.button("Close", on_click=dialog.close).props("flat icon=close")
        
        # Content
        content = ui.row().classes("w-full flex-wrap gap-2 overflow-y-auto p-2 border bg-gray-50 rounded h-full")
        def refresh_trash_ui():
            content.clear()
            items = get_trash_items()
            with content:
                if not items:
                    ui.label("Recycle Bin is empty.").classes("text-gray-400 italic")
                for item in items:
                    make_item_button(item, is_trash=True)
                    
        refresh_trash_ui()

        # Footer actions
        def do_empty_trash():
            with ui.dialog() as confirm, ui.card():
                 ui.label("Permanently delete ALL items?").classes("font-bold text-red-600")
                 with ui.row().classes("mt-4 justify-end"):
                     ui.button("Cancel", on_click=confirm.close).props("flat")
                     def confirm_empty():
                         empty_trash()
                         confirm.close()
                         refresh_trash_ui()
                         ui.notify("Trash Emptied")
                     ui.button("Empty Trash", color="red", on_click=confirm_empty)
            confirm.open()

        with ui.row().classes("w-full justify-end mt-4"):
            ui.button("Empty Trash", icon="delete_forever", on_click=do_empty_trash).props("flat color=red")


    # Define helpers visible to make_item_button (or injected)
    # Since make_item_button is global, we need these global or passed
    # but make_item_button calls global restore_from_trash check below
    dialog.open()
    return dialog

def restore_from_trash(item):
    restore_item(item["id"])
    ui.notify(f"Restored {item['label']}")
    # Refresh the trash UI? We need reference to content or close/reopen
    # simpler to just close/reopen or trigger global refresh but trash is in dialog
    # For now, let's close and reopen or use a reactive approach?
    # Simpler: notify user and they can see it gone if we refresh current dialog items
    # but refresh_trash_ui is inside open_recycle_bin scope...
    # Hack: close and reopen? No.
    # We should fix make_item_button to accept callbacks or refactor context.
    # Refactor: We can just let the trash_dialog content be refreshed.
    if trash_dialog:
        trash_dialog.close()
        open_recycle_bin()
    refresh_grid()

def delete_forever(item):
    with ui.dialog() as confirm, ui.card():
         ui.label(f"Permanently delete {item['label']}?").classes("font-bold")
         with ui.row().classes("mt-4 justify-end"):
             ui.button("Cancel", on_click=confirm.close).props("flat")
             def do_del():
                 permanent_delete_item(item["id"])
                 confirm.close()
                 if trash_dialog:
                    trash_dialog.close()
                    open_recycle_bin()
                 ui.notify("Permanently Deleted")
             ui.button("Delete", color="red", on_click=do_del)
    confirm.open()


# --------------------------------------------------
# PIN Dialog & Animation
# --------------------------------------------------

def open_pin_dialog(on_success):
    """
    Opens a PIN dialog with a 'fun' wall of floating number bubbles.
    """
    success_flag = {"granted": False}
    
    with ui.dialog() as dialog, ui.card().classes("w-full h-full p-0 items-center justify-center bg-transparent shadow-none bg-blue-900") as background_card:
        dialog.props("maximized transition-show=fade transition-hide=fade")
        
        # Handle dialog dismissal (clicking outside or pressing ESC)
        def on_dialog_close():
            if not success_flag["granted"]:
                # User dismissed without entering correct PIN
                #ui.notify("Admin Mode Cancelled", color="grey")
                print('Admin Mode Cancelled')

        dialog.on("hide", on_dialog_close)
        
        # Click on background to close (using JavaScript to check if click is directly on background)
        background_card.on("click", lambda e: dialog.close(), js_handler="""
            (e) => {
                // Only close if clicking directly on the background, not on child elements
                if (e.target === e.currentTarget) {
                    return true;
                }
                return false;
            }
        """)
        
        # 1. Floating Bubbles Background (Fun visual)
        with ui.element("div").classes("absolute inset-0 overflow-hidden pointer-events-none"):
            # Inject CSS for animation
            ui.html("""
            <style>
                @keyframes floatUp {
                    0% { transform: translateY(110vh) scale(0.5); opacity: 0; }
                    10% { opacity: 0.7; }
                    90% { opacity: 0.7; }
                    100% { transform: translateY(-10vh) scale(1.2); opacity: 0; }
                }
                .bubble {
                    position: absolute;
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    color: rgba(255, 255, 255, 0.8);
                    font-weight: bold;
                    font-family: monospace;
                    backdrop-filter: blur(2px);
                    background: rgba(255, 255, 255, 0.1);
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                    animation-name: floatUp;
                    animation-timing-function: linear;
                    animation-iteration-count: infinite;
                }
            </style>
            """, sanitize=False)
            
            # Create random bubbles
            for _ in range(40):
                size = random.randint(40, 100)
                left = random.randint(0, 100)
                duration = random.uniform(5, 15)
                delay = random.uniform(0, 5)
                fs = random.randint(20, 50)
                num = random.randint(0, 99)
                
                (ui.label(str(num))
                 .classes("bubble")
                 .style(f"width: {size}px; height: {size}px; left: {left}%; "
                        f"animation-duration: {duration}s; animation-delay: -{delay}s; "
                        f"font-size: {fs}px;"))

        # 2. Main PIN Entry Card
        with ui.card().classes("z-10 w-80 p-8 shadow-2xl rounded-xl bg-white/95 items-center gap-4 anim-bounce-in"):
            ui.label("Admin Access").classes("text-2xl font-bold text-blue-900")
            ui.label("Enter PIN").classes("text-gray-500 text-sm")
            
            pin_input = ui.input(password=True).classes("w-full text-center text-xl tracking-widest").props("outlined placeholder='****' inputmode='numeric' pattern='[0-9]*' autocomplete='off'")
            
            def check_pin():
                # Load PIN from config
                config = read_config()
                stored_pin = config.get("pin", "1234")
                
                if pin_input.value == stored_pin:
                    success_flag["granted"] = True
                    #ui.notify("Access Granted! Admin Mode Enabled", color="green")
                    dialog.close()
                    on_success()
                else:
                    #ui.notify("Incorrect PIN!", color="red")
                    pin_input.value = ""
                    dialog.close()
                    #pin_input.run_method("focus")
                    # Shake effect? (Optional, maybe later)

            with ui.row().classes("w-full justify-center gap-4 mt-2"):
                ui.button("Cancel", on_click=dialog.close).props("flat color=grey")
                ui.button("Unlock", on_click=check_pin).classes("bg-blue-600 text-white w-24")
                
            # Press enter to submit
            pin_input.on('keydown.enter', check_pin)

    dialog.open()

def open_change_pin_dialog():
    with ui.dialog() as dialog, ui.card().classes("z-10 w-80 p-8 shadow-2xl rounded-xl bg-white/95 items-center gap-4"):
        ui.label("Change PIN").classes("text-2xl font-bold text-blue-900")
        ui.label("Enter New PIN").classes("text-gray-500 text-sm")
        
        pin_input = ui.input(password=True).classes("w-full text-center text-xl tracking-widest").props("outlined placeholder='****' inputmode='numeric' pattern='[0-9]*' autocomplete='off'")
        
        def save_pin():
            if len(pin_input.value) == 4 and pin_input.value.isdigit():
                # Save the new PIN to config
                try:
                    config = read_config()
                    config["pin"] = pin_input.value
                    write_config(config)
                    ui.notify("PIN Changed Successfully!", color="green")
                    dialog.close()
                except Exception as e:
                    ui.notify(f"Error saving PIN: {e}", color="red")
            else:
                ui.notify("Please enter a valid 4-digit PIN", color="orange")
                pin_input.value = ""

        with ui.row().classes("w-full justify-center gap-4 mt-2"):
            ui.button("Cancel", on_click=dialog.close).props("flat color=grey")
            ui.button("Save", on_click=save_pin).classes("bg-blue-600 text-white w-24")
            
        # Press enter to submit
        pin_input.on('keydown.enter', save_pin)

    dialog.open()

def open_secret_dialog():
    """Dialog to update OpenSymbols API Secret."""
    
    # Get current secret (masked)
    config = read_config()
    current_secret = config.get("opensymbols_secret", "")
    masked = current_secret[:6] + "..." + current_secret[-4:] if current_secret and len(current_secret) > 10 else "Not Set"

    with ui.dialog() as dialog, ui.card().classes("z-10 w-96 p-8 shadow-2xl rounded-xl bg-white/95 items-center gap-4"):
        ui.label("OpenSymbols API Secret").classes("text-xl font-bold text-blue-900")
        ui.link("Get Secret Here", "https://www.opensymbols.org/api#secret", new_tab=True).classes("text-sm text-blue-500 underline mb-2")
        ui.label(f"Current: {masked}").classes("text-xs text-gray-500 mb-2")
        
        secret_input = ui.input("New Secret").classes("w-full").props("outlined placeholder='Paste new secret here' clearable")
        
        def save():
            if secret_input.value:
                update_secret(secret_input.value.strip())
                ui.notify("Secret updated! Token cache cleared.", color="green")
                dialog.close()
            else:
                ui.notify("Please enter a valid secret", color="orange")

        test_btn = None
        
        def test():
            if not test_btn: return
            
            # Reset
            test_btn.props("icon=hourglass_empty color=grey")
            
            # Test entered value OR current config value if empty
            val_to_test = secret_input.value.strip() if secret_input.value else current_secret
            
            if not val_to_test:
                ui.notify("No secret to test!", color="orange")
                test_btn.props("icon=help color=grey")
                return
                
            ui.notify("Testing...", color="blue")
            success, msg = test_secret(val_to_test)
            
            if success:
                ui.notify(msg, color="green")
                test_btn.props("icon=check color=green")
            else:
                ui.notify(msg, color="red", multi_line=True, timeout=5000)
                test_btn.props("icon=close color=red")

        with ui.row().classes("w-full justify-end gap-2 mt-4"):
             test_btn = ui.button("Test", on_click=test).props("flat color=grey icon=help")
             ui.button("Cancel", on_click=dialog.close).props("flat")
             ui.button("Save", on_click=save).classes("bg-blue-600 text-white")

    dialog.open()


# --------------------------------------------------
# Sentence Builder Bar
# --------------------------------------------------

def render_sentence_bar():
    if not sentence_bar_container:
        return

    sentence_bar_container.clear()

    if not is_sentence_mode["value"]:
        return

    with sentence_bar_container:
        with ui.card().classes("w-full sticky top-0 z-50 bg-white border-b-4 border-green-400 shadow-lg p-0 mb-2"):

            # Row 1: Sentence strip (scrollable, taller items)
            with ui.row().classes("w-full overflow-x-auto gap-3 p-3 bg-gray-50 min-h-[8rem] items-center flex-nowrap user-select-none") as queue_container:
                queue_container.props('id="sortable-queue"')

                if not sentence_queue:
                    ui.label("Tap words below to build a sentence...").classes("text-gray-400 italic text-lg ml-2")

                for i, item in enumerate(sentence_queue):
                    img_src = None
                    if item["image_path"]:
                        if item["image_path"].startswith("http"):
                            img_src = item["image_path"]
                        elif os.path.isabs(item["image_path"]):
                            try:
                                rel_path = os.path.relpath(item["image_path"], str(DATA_DIR))
                                img_src = f"/data/{rel_path}"
                            except ValueError:
                                img_src = None

                    def remove_at(idx=i):
                        sentence_queue.pop(idx)
                        refresh_sentence_bar()

                    with ui.column().classes("w-20 h-24 bg-white border-2 border-gray-200 rounded-xl shadow flex-shrink-0 p-1 items-center gap-0 justify-between handle cursor-pointer relative hover:border-red-300 transition-colors").on("click", remove_at):
                        if img_src:
                            ui.image(img_src).classes("w-full h-14 object-cover rounded-lg pointer-events-none")
                        else:
                            with ui.column().classes("w-full h-14 bg-gray-100 items-center justify-center rounded-lg pointer-events-none"):
                                ui.icon("image").classes("text-sm text-gray-300")
                        ui.label(item["label"]).classes("text-xs font-bold leading-tight text-center overflow-hidden w-full text-ellipsis pointer-events-none")
                        # Tap-to-remove hint
                        ui.icon("cancel").classes("absolute -top-1 -right-1 text-base text-red-400 bg-white rounded-full pointer-events-none")

            # Attach SortableJS
            def handle_reorder(e):
                try:
                    detail = e.args.get('detail', {})
                    old_idx = detail.get('oldIndex')
                    new_idx = detail.get('newIndex')
                    if old_idx is not None and new_idx is not None:
                        if 0 <= old_idx < len(sentence_queue) and 0 <= new_idx < len(sentence_queue):
                            item = sentence_queue.pop(old_idx)
                            sentence_queue.insert(new_idx, item)
                            refresh_sentence_bar()
                        else:
                            print(f"DEBUG: Indices out of bounds: old={old_idx}, new={new_idx}, len={len(sentence_queue)}")
                    else:
                        print(f"DEBUG: Invalid event args: {e.args}")
                except Exception as ex:
                    print(f"Sort error: {ex}")

            queue_container.on('sort_change', handle_reorder)

            def handle_spill(e):
                try:
                    detail = e.args.get('detail', {})
                    old_idx = detail.get('oldIndex')
                    if old_idx is not None and 0 <= old_idx < len(sentence_queue):
                        sentence_queue.pop(old_idx)
                        refresh_sentence_bar()
                except Exception as ex:
                    print(f"Spill remove error: {ex}")

            queue_container.on('item_spilled', handle_spill)

            ui.run_javascript('''
                var el = document.getElementById('sortable-queue');
                if (el) {
                    new Sortable(el, {
                        animation: 150,
                        ghostClass: 'sortable-ghost',
                        removeOnSpill: true,
                        onSpill: function(evt) {
                            el.dispatchEvent(new CustomEvent('item_spilled', {
                                detail: { oldIndex: evt.oldIndex }
                            }));
                        },
                        onEnd: function(evt) {
                            if (evt.to === el) {
                                el.dispatchEvent(new CustomEvent('sort_change', {
                                    detail: { oldIndex: evt.oldIndex, newIndex: evt.newIndex }
                                }));
                            }
                        }
                    });
                }
            ''')

            # Row 2: Controls
            def backspace():
                if sentence_queue:
                    sentence_queue.pop()
                    refresh_sentence_bar()

            def clear():
                with ui.dialog() as confirm_dlg, ui.card():
                    ui.label("Clear the whole sentence?").classes("text-lg font-bold")
                    with ui.row().classes("w-full justify-end gap-2 mt-4"):
                        ui.button("Cancel", on_click=confirm_dlg.close).props("flat")
                        def do_clear():
                            confirm_dlg.close()
                            sentence_queue.clear()
                            refresh_sentence_bar()
                        ui.button("Clear", icon="delete_sweep", on_click=do_clear).props("unelevated color=red")
                confirm_dlg.open()

            texts = [(item.get("tts_text") or item["label"]).replace('"', '\\"').replace("'", "\\'") for item in sentence_queue]
            js_array = "[" + ",".join([f'"{t}"' for t in texts]) + "]"

            play_js = f'''
                (e) => {{
                    const texts = {js_array};
                    window.speechSynthesis.cancel();
                    window.speechSynthesis.resume();
                    let index = 0;
                    function speakNext() {{
                        if (index < texts.length) {{
                            const u = new SpeechSynthesisUtterance(texts[index]);
                            u.rate = 1.3;
                            u.pitch = 1.0;
                            u.volume = 1.0;
                            u.onend = () => {{ index++; speakNext(); }};
                            window.speechSynthesis.speak(u);
                        }}
                    }}
                    speakNext();
                }}
            '''

            with ui.row().classes("w-full items-stretch px-3 py-2 bg-white gap-3"):
                ui.button("UNDO", icon="backspace", on_click=backspace) \
                    .props("unelevated size=xl color=orange") \
                    .classes("flex-1 text-lg font-bold")
                ui.button("CLEAR", icon="delete_sweep", on_click=clear) \
                    .props("unelevated size=xl color=red") \
                    .classes("flex-1 text-lg font-bold")
                ui.button("SPEAK", icon="play_arrow", on_click=None) \
                    .props("unelevated size=xl color=green") \
                    .classes("flex-1 text-xl font-extrabold") \
                    .on("click", js_handler=play_js)


# --------------------------------------------------
# Main UI Refresher
# --------------------------------------------------

def render_grid():
    if not grid_container:
        return
        
    grid_container.clear()
    
    categories = get_categories()
    
    with grid_container:
        # Admin Toolbar (Only if Admin)
        if is_admin_mode["value"]:
            with ui.row().classes("w-full bg-gray-100 p-2 rounded shadow-inner mb-4 mt-2 justify-start gap-4"):
                 ui.button("Add Item", icon="add", on_click=lambda: open_add_item_dialog(None)).classes("bg-blue-600 text-white")
                 ui.button("Add Category", icon="create_new_folder", on_click=open_add_category_dialog).classes("bg-blue-600 text-white")
                 ui.button("Change Pin", icon="lock", on_click=open_change_pin_dialog).classes("bg-blue-600 text-white")
                 ui.button("API Key", icon="key", on_click=open_secret_dialog).classes("bg-blue-600 text-white")
                 ui.space()
                 ui.button("Recycle Bin", icon="delete", on_click=open_recycle_bin).props("flat color=grey")

        # Colour map: name → (items bg, header bg, header text)
        cat_color_map = {
            "orange": ("bg-orange-50",  "bg-orange-200",  "text-orange-900"),
            "yellow": ("bg-yellow-50",  "bg-yellow-200",  "text-yellow-900"),
            "green":  ("bg-green-50",   "bg-green-200",   "text-green-900"),
            "blue":   ("bg-blue-50",    "bg-blue-200",    "text-blue-900"),
            "purple": ("bg-purple-50",  "bg-purple-200",  "text-purple-900"),
            "teal":   ("bg-teal-50",    "bg-teal-200",    "text-teal-900"),
            "pink":   ("bg-pink-50",    "bg-pink-200",    "text-pink-900"),
            "indigo": ("bg-indigo-50",  "bg-indigo-200",  "text-indigo-900"),
            "red":    ("bg-red-50",     "bg-red-200",     "text-red-900"),
            "gray":   ("bg-gray-50",    "bg-gray-200",    "text-gray-900"),
        }
        default_palette = list(cat_color_map.values())

        for idx, cat in enumerate(categories):
            # Visibility Check (Category)
            is_cat_visible = cat.get("visible", True)
            if not is_cat_visible and not is_admin_mode["value"]:
                continue

            cat_opacity = "opacity-50" if not is_cat_visible else ""
            stored_color = cat.get("color")
            if stored_color and stored_color.startswith("#"):
                # Custom hex color — compute light tint for items area
                r = int(stored_color[1:3], 16)
                g = int(stored_color[3:5], 16)
                b = int(stored_color[5:7], 16)
                brightness = (r * 299 + g * 587 + b * 114) / 1000
                header_text = "text-white" if brightness < 128 else "text-gray-900"
                bg_header_cls, bg_header_sty = "", f"background-color:{stored_color};"
                bg_light_cls,  bg_light_sty  = "", f"background-color:rgba({r},{g},{b},0.15);"
            else:
                bg_light_cls, bg_header_cls, header_text = (
                    cat_color_map[stored_color] if stored_color in cat_color_map
                    else default_palette[idx % len(default_palette)]
                )
                bg_header_sty = bg_light_sty = ""

            with ui.column().classes(f"w-full mb-4 rounded-2xl overflow-hidden shadow-sm gap-0 {cat_opacity}"):
                # Coloured category header
                with ui.row().classes(f"w-full items-center justify-between px-4 py-3 {bg_header_cls}").style(bg_header_sty):
                    ui.label(cat["name"]).classes(f"text-2xl font-extrabold {header_text}")

                    if is_admin_mode["value"]:
                        def toggle_cat_vis(c_id=cat["id"]):
                            toggle_category_visibility(c_id)
                            refresh_grid()

                        def rename_cat(c_id=cat["id"], c_name=cat["name"], c_color=cat.get("color")):
                            with ui.dialog() as d, ui.card().classes("w-96"):
                                ui.label(f"Edit Category").classes("font-bold text-lg")
                                new_name_input = ui.input("Name", value=c_name).classes("w-full")

                                ui.label("Colour:").classes("text-sm font-bold mt-3")
                                is_custom_init = bool(c_color and c_color.startswith("#"))
                                selected = {"color": c_color}

                                swatch_colors = {
                                    "orange": "#fed7aa", "yellow": "#fef08a", "green":  "#bbf7d0",
                                    "blue":   "#bfdbfe", "purple": "#e9d5ff", "teal":   "#99f6e4",
                                    "pink":   "#fbcfe8", "indigo": "#c7d2fe", "red":    "#fecaca",
                                    "gray":   "#e5e7eb",
                                }

                                swatch_container = ui.row().classes("gap-3 flex-wrap mt-1")

                                # Custom colour input — shown when custom swatch is active
                                custom_row = ui.row().classes("w-full items-center gap-2 mt-2")
                                custom_row.set_visibility(is_custom_init)
                                with custom_row:
                                    ui.label("Custom:").classes("text-sm text-gray-600")
                                    color_input = ui.color_input(
                                        value=c_color if is_custom_init else "#ff6b6b"
                                    ).classes("w-36")

                                def render_swatches():
                                    swatch_container.clear()
                                    is_custom_sel = bool(
                                        selected["color"] and selected["color"].startswith("#")
                                    )
                                    with swatch_container:
                                        # Named swatches
                                        for cn, hx in swatch_colors.items():
                                            is_sel = selected["color"] == cn
                                            border = "3px solid #1f2937" if is_sel else "2px solid #d1d5db"

                                            def on_click(color=cn):
                                                selected["color"] = color
                                                custom_row.set_visibility(False)
                                                render_swatches()

                                            with ui.element("div").style(
                                                f"width:36px; height:36px; border-radius:50%; background:{hx};"
                                                f"border:{border}; cursor:pointer; display:flex;"
                                                f"align-items:center; justify-content:center;"
                                            ).on("click", on_click).tooltip(cn.capitalize()):
                                                if is_sel:
                                                    ui.icon("check").style("font-size:18px; color:#1f2937;")

                                        # Custom swatch — rainbow when unset, actual hex when active
                                        custom_sty = (
                                            f"background-color:{selected['color']};" if is_custom_sel
                                            else "background:conic-gradient(red,yellow,lime,cyan,blue,magenta,red);"
                                        )
                                        border = "3px solid #1f2937" if is_custom_sel else "2px solid #d1d5db"
                                        icon_color = "#fff" if not is_custom_sel else "#1f2937"

                                        def on_custom_click():
                                            selected["color"] = color_input.value
                                            custom_row.set_visibility(True)
                                            render_swatches()

                                        with ui.element("div").style(
                                            f"width:36px; height:36px; border-radius:50%; {custom_sty}"
                                            f"border:{border}; cursor:pointer; display:flex;"
                                            f"align-items:center; justify-content:center;"
                                        ).on("click", on_custom_click).tooltip("Custom colour"):
                                            if is_custom_sel:
                                                ui.icon("check").style(f"font-size:18px; color:{icon_color};")
                                            else:
                                                ui.icon("palette").style(f"font-size:16px; color:{icon_color};")

                                render_swatches()

                                def save():
                                    if not new_name_input.value:
                                        return
                                    new_name = new_name_input.value
                                    # If custom wheel is open, use its current value
                                    final_color = (
                                        color_input.value
                                        if selected["color"] and selected["color"].startswith("#")
                                        else selected["color"]
                                    )
                                    if new_name != c_name:
                                        if not rename_category(c_id, new_name):
                                            ui.notify("Error renaming (name exists?)", color="red")
                                            return
                                        final_id = new_name
                                    else:
                                        final_id = c_id
                                    set_category_color(final_id, final_color)
                                    d.close()
                                    refresh_grid()

                                ui.button("Save", on_click=save).classes("mt-4 w-full")
                            d.open()

                        def delete_cat(c_id=cat["id"], c_name=cat["name"]):
                            with ui.dialog() as d, ui.card():
                                ui.label(f"Delete Category '{c_name}'?").classes("font-bold text-lg")
                                ui.label("All items in this category will be moved to the Recycle Bin.").classes("text-sm text-gray-600")
                                with ui.row().classes("w-full justify-end mt-4 gap-1"):
                                    ui.button("Cancel", on_click=d.close).props("flat")
                                    def confirm():
                                        delete_category(c_id)
                                        d.close()
                                        refresh_grid()
                                        ui.notify(f"Deleted Category: {c_name}")
                                    ui.button("Delete", color="red", on_click=confirm)
                            d.open()

                        def move_up(c_id=cat["id"]):
                            if move_category_up(c_id):
                                ui.notify("Moved up")
                                refresh_grid()

                        def move_down(c_id=cat["id"]):
                            if move_category_down(c_id):
                                ui.notify("Moved down")
                                refresh_grid()

                        with ui.row().classes("gap-1"):
                            ui.button(icon="arrow_upward", on_click=move_up).props("flat dense color=purple round").tooltip("Move Up")
                            ui.button(icon="arrow_downward", on_click=move_down).props("flat dense color=purple round").tooltip("Move Down")
                            ui.button(icon="edit", on_click=rename_cat).props("flat dense color=blue round").tooltip("Rename Category")
                            ui.button(icon="delete", on_click=delete_cat).props("flat dense color=red round").tooltip("Delete Category")

                # Items area with matching light tint
                items = get_items(cat["id"])
                visible_items = [i for i in items if i.get("visible", True) or is_admin_mode["value"]]

                with ui.row().classes(f"w-full flex-wrap gap-2 p-3 {bg_light_cls}").style(bg_light_sty):
                    for item in visible_items:
                        make_item_button(item)

                    if not visible_items:
                        ui.label("No items.").classes("text-gray-400 italic text-sm ml-2")
        


@ui.page('/')
@ui.page('/grid')
def grid_view_page():
    global sentence_bar_container
    setup_header()
    ui.query('.nicegui-content').classes('p-0 gap-0')

    cat_color_map = {
        "orange": ("bg-orange-50",  "bg-orange-200",  "text-orange-900"),
        "yellow": ("bg-yellow-50",  "bg-yellow-200",  "text-yellow-900"),
        "green":  ("bg-green-50",   "bg-green-200",   "text-green-900"),
        "blue":   ("bg-blue-50",    "bg-blue-200",    "text-blue-900"),
        "purple": ("bg-purple-50",  "bg-purple-200",  "text-purple-900"),
        "teal":   ("bg-teal-50",    "bg-teal-200",    "text-teal-900"),
        "pink":   ("bg-pink-50",    "bg-pink-200",    "text-pink-900"),
        "indigo": ("bg-indigo-50",  "bg-indigo-200",  "text-indigo-900"),
        "red":    ("bg-red-50",     "bg-red-200",     "text-red-900"),
        "gray":   ("bg-gray-50",    "bg-gray-200",    "text-gray-900"),
    }
    default_palette = list(cat_color_map.values())

    page_col = ui.column().classes("w-full p-0 gap-0")

    def refresh_page():
        global sentence_bar_container
        page_col.clear()
        with page_col:
            # Header — same structure as main screen
            with ui.row().classes("w-full items-center justify-between px-3 py-2 bg-white shadow-sm"):
                ui.label("Dxtr Speaks").classes("text-3xl font-extrabold text-blue-900") \
                    .on('click', lambda: ui.navigate.to('/home'))
                with ui.row().classes("items-center gap-2"):
                    ui.button("Large", icon="grid_view", on_click=lambda: ui.navigate.to('/home')) \
                        .props("unelevated size=lg color=blue")

                    def click_sentence_mode():
                        is_sentence_mode["value"] = not is_sentence_mode["value"]
                        refresh_page()
                    if is_sentence_mode["value"]:
                        ui.button("Build", icon="record_voice_over", on_click=click_sentence_mode) \
                            .props("unelevated size=lg color=green")
                    else:
                        ui.button("Build", icon="record_voice_over", on_click=click_sentence_mode) \
                            .props("outline size=lg color=green")

                    def click_admin():
                        if is_admin_mode["value"]:
                            is_admin_mode["value"] = False
                            refresh_page()
                        else:
                            def on_success():
                                is_admin_mode["value"] = True
                                refresh_page()
                            open_pin_dialog(on_success)
                    if is_admin_mode["value"]:
                        ui.button("Admin", icon="settings", on_click=click_admin) \
                            .props("unelevated size=lg color=red")
                    else:
                        ui.button("Admin", icon="settings", on_click=click_admin) \
                            .props("outline size=lg color=grey")

            # Sentence bar (shared global)
            sentence_bar_container = ui.column().classes("w-full sticky top-0 z-50 p-0")
            render_sentence_bar()

            # Suppress shadows/rounding on item cards inside the compact grid
            ui.add_head_html('''<style>
                .compact-grid .item-card { box-shadow: none !important; }
            </style>''')

            # Categories grid container — no padding, no gaps
            grid_div = ui.column().classes("w-full p-0 gap-0 compact-grid")

            def render(size):
                grid_item_size["value"] = size
                grid_div.clear()
                categories = get_categories()
                with grid_div:
                    if is_admin_mode["value"]:
                        with ui.row().classes("w-full bg-gray-100 p-2 justify-start gap-4 items-center flex-wrap"):
                            ui.button("Add Item", icon="add", on_click=lambda: open_add_item_dialog(None)) \
                                .classes("bg-blue-600 text-white")
                            ui.button("Add Category", icon="create_new_folder", on_click=open_add_category_dialog) \
                                .classes("bg-blue-600 text-white")
                            ui.space()
                            ui.label("Item size:").classes("text-sm font-semibold text-gray-600")
                            _slider = ui.slider(min=60, max=300, value=size, step=10).classes("w-32")
                            _slider.on('update:model-value', lambda e: render(e.args), throttle=0.15)
                            ui.space()
                            ui.button("Recycle Bin", icon="delete", on_click=open_recycle_bin) \
                                .props("flat color=grey")

                    for idx, cat in enumerate(categories):
                        if not cat.get("visible", True) and not is_admin_mode["value"]:
                            continue

                        stored_color = cat.get("color")
                        if stored_color and stored_color.startswith("#"):
                            r = int(stored_color[1:3], 16)
                            g = int(stored_color[3:5], 16)
                            b = int(stored_color[5:7], 16)
                            brightness = (r * 299 + g * 587 + b * 114) / 1000
                            header_text = "text-white" if brightness < 128 else "text-gray-900"
                            bg_header_cls, bg_header_sty = "", f"background-color:{stored_color};"
                            bg_light_cls,  bg_light_sty  = "", f"background-color:rgba({r},{g},{b},0.15);"
                        else:
                            bg_light_cls, bg_header_cls, header_text = (
                                cat_color_map[stored_color] if stored_color in cat_color_map
                                else default_palette[idx % len(default_palette)]
                            )
                            bg_header_sty = bg_light_sty = ""

                        cat_opacity = "opacity-50" if not cat.get("visible", True) else ""
                        with ui.column().classes(f"w-full gap-0 {cat_opacity}"):
                            # Thin header band
                            with ui.row().classes(f"w-full items-center px-2 py-1 {bg_header_cls}").style(bg_header_sty):
                                ui.label(cat["name"]).classes(f"text-sm font-semibold {header_text}")

                            items = get_items(cat["id"])
                            visible_items = [i for i in items if i.get("visible", True) or is_admin_mode["value"]]

                            with ui.row().classes(f"w-full flex-wrap gap-0 p-0 {bg_light_cls}").style(bg_light_sty):
                                for item in visible_items:
                                    make_item_button(item, size_px=size)
                                if not visible_items:
                                    ui.label("No items.").classes("text-gray-400 italic text-sm ml-2")

            render(grid_item_size["value"])

    refresh_page()

def refresh_sentence_bar():
    render_sentence_bar()

def refresh_grid():
    render_grid()

def refresh_ui():
    """Build the single-page vertical layout."""
    global sentence_bar_container, grid_container
    
    ui.query('.nicegui-content').classes('p-0 gap-0')
        # 1. Clear the main container
    if main_column:
        main_column.clear()
        
        # 2. Rebuild the layout
        with main_column.classes("p-0 gap-0")   :
            # Main Header
            with ui.row().classes("w-full items-center justify-between px-3 py-2"):
                ui.label("Dxtr Speaks").classes("text-3xl font-extrabold text-blue-900").on('click', refresh_ui)
                with ui.row().classes("items-center gap-2"):

                    # Grid View
                    ui.button("Compact", icon="grid_view", on_click=lambda: ui.navigate.to('/grid')) \
                        .props("unelevated size=lg color=blue")

                    # Sentence Mode Toggle
                    def click_sentence_mode():
                        is_sentence_mode["value"] = not is_sentence_mode["value"]
                        refresh_ui()
                    if is_sentence_mode["value"]:
                        ui.button("Build", icon="record_voice_over", on_click=click_sentence_mode) \
                            .props("unelevated size=lg color=green")
                    else:
                        ui.button("Build", icon="record_voice_over", on_click=click_sentence_mode) \
                            .props("outline size=lg color=green")

                    # Admin Mode Toggle
                    def click_admin():
                        if is_admin_mode["value"]:
                            is_admin_mode["value"] = False
                            refresh_ui()
                        else:
                            def on_success():
                                is_admin_mode["value"] = True
                                refresh_ui()
                            open_pin_dialog(on_success)
                    if is_admin_mode["value"]:
                        ui.button("Admin", icon="settings", on_click=click_admin) \
                            .props("unelevated size=lg color=red")
                    else:
                        ui.button("Admin", icon="settings", on_click=click_admin) \
                            .props("outline size=lg color=grey")
            
            # Sentence Bar
            sentence_bar_container = ui.column().classes("w-full sticky top-0 z-50 p-0")
            render_sentence_bar()
            
            # Main Grid
            grid_container = ui.column().classes("w-full p-0 gap-0")
            render_grid()


# --------------------------------------------------
# Layout Setup
# --------------------------------------------------

@ui.page('/home')
def index_page():
    global main_column
    
    setup_header()
    
    # Ensure styles
    ui.query('.nicegui-content').classes('p-0 gap-0') 
    
    with ui.column().classes("w-full p-0 gap-0") as col:
        main_column = col
        refresh_ui()

if __name__ in {"__main__", "__mp_main__"}:
    ui.run(host='0.0.0.0', port=8085, title="Dxtr AAC", favicon="🗣️")
