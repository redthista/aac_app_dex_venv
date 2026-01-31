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
    toggle_item_visibility,
    move_category_up,
    move_category_down,
    read_config,
    write_config,
    DATA_DIR
)
import os
import base64
import random
import yaml

# Serve the data directory for images
app.add_static_files('/data', str(DATA_DIR))

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

# Remove default padding and gap
ui.query('nicegui-content').classes('gap-0 p-0')

# --------------------------------------------------
# UI Component: Item Button
# --------------------------------------------------

def make_item_button(item, is_trash=False):
    """Create clickable item button with image support."""

    is_visible = item.get("visible", True)
    # Added flex flex-col so flex-grow works, and item-card class for iOS touch support
    base_classes = "item-card w-32 h-40 m-2 p-0 gap-0 flex flex-col items-center hover:scale-105 transition-transform cursor-pointer shadow-md relative"
    if not is_visible:
        base_classes += " opacity-50 grayscale border-2 border-dashed"
        
    card = ui.card().classes(base_classes)
    
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

        ui.label("Update Image:").classes("text-sm font-bold mt-2")
        
        uploaded_file = {"data": None}
        
        # Fallback Upload
        ui.upload(on_upload=lambda e: handle_file_upload(e, uploaded_file), auto_upload=True).props("accept=image/* flat dense").classes("w-full mt-1")

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
        
        uploaded_file = {"data": None}
        
        ui.upload(on_upload=lambda e: handle_file_upload(e, uploaded_file), auto_upload=True).props("accept=image/* flat dense").classes("w-full mt-1")

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
        with ui.card().classes("w-full sticky top-0 z-50 bg-blue-50 border-b-2 border-blue-200 mb-4 p-2 shadow-md"):
            with ui.row().classes("w-full items-center gap-2"):
                # Queue Display
                # Sortable container
                with ui.row().classes("flex-grow overflow-x-auto gap-2 p-2 bg-white rounded border border-gray-200 min-h-[5rem] items-center flex-nowrap user-select-none") as queue_container:
                    # Add ID for SortableJS
                    queue_container.props('id="sortable-queue"')
                    
                    if not sentence_queue:
                        ui.label("Tap items to build a sentence...").classes("text-gray-400 italic ml-2")
                    
                    for i, item in enumerate(sentence_queue):
                         # Small thumbnail version of item
                         # Use ui.card for better structure, but ui.column is fine. 
                         # IMPORTANT: data-id is helpful for tracking if we needed it, but using indices is simpler.
                         with ui.column().classes("w-16 h-20 bg-white border rounded shadow-sm flex-shrink-0 p-1 items-center gap-0 justify-between handle cursor-move"):
                            # Image path resolution (similar to make_item_button)
                            img_src = None
                            if item["image_path"]:
                                if item["image_path"].startswith("http"):
                                    img_src = item["image_path"]
                                elif os.path.isabs(item["image_path"]):
                                    try:
                                        # Need a robustway to display, assuming DATA_DIR is available in scope or imports
                                        rel_path = os.path.relpath(item["image_path"], str(DATA_DIR))
                                        img_src = f"/data/{rel_path}"
                                    except ValueError:
                                        img_src = None
                            
                            if img_src:
                                ui.image(img_src).classes("w-full h-12 object-cover rounded pointer-events-none")
                            else:
                                with ui.column().classes("w-full h-12 bg-gray-100 items-center justify-center rounded pointer-events-none"):
                                    ui.icon("image").classes("text-xs text-gray-300")
                            
                            ui.label(item["label"]).classes("text-[10px] leading-tight text-center overflow-hidden w-full text-ellipsis pointer-events-none")

                # Attach SortableJS to the queue_container 
                def handle_reorder(e):
                    try:
                        # Correctly access nested detail
                        detail = e.args.get('detail', {})
                        old_idx = detail.get('oldIndex')
                        new_idx = detail.get('newIndex')
                        
                        # Move item in list
                        if old_idx is not None and new_idx is not None:
                            if 0 <= old_idx < len(sentence_queue) and 0 <= new_idx < len(sentence_queue):
                                item = sentence_queue.pop(old_idx)
                                sentence_queue.insert(new_idx, item)
                                
                                # ui.notify(f"Moved '{item['label']}'")
                                
                                # Refresh the UI so the Play button gets the new order
                                refresh_sentence_bar()
                            else:
                                print(f"DEBUG: Indices out of bounds: old={old_idx}, new={new_idx}, len={len(sentence_queue)}")
                        else:
                            print(f"DEBUG: Invalid event args: {e.args}")
                            
                    except Exception as ex:
                        print(f"Sort error: {ex}")
                        ui.notify(f"Sort error: {ex}", color="red")

                # Listen for custom sort event
                queue_container.on('sort_change', handle_reorder)
                
                # Initialize Sortable
                ui.run_javascript('''
                    var el = document.getElementById('sortable-queue');
                    if (el) {
                        new Sortable(el, {
                            animation: 150,
                            ghostClass: 'sortable-ghost',
                            onEnd: function (evt) {
                                // Emit custom event to NiceGUI
                                // getElement() helper not strictly needed if we dispatch to the element itself
                                const event = new CustomEvent('sort_change', {
                                    detail: { oldIndex: evt.oldIndex, newIndex: evt.newIndex } 
                                });
                                // We need to dispatch it on the widget's DOM element that NiceGUI is listening to.
                                // In NiceGUI 1.0+, the element ID matches the widget ID.
                                // But here we assigned id="sortable-queue" via props.
                                // NiceGUI listens to events on the element.
                                el.dispatchEvent(event);
                            }
                        });
                    }
                ''')

                # Controls
                with ui.row().classes("flex-shrink-0 gap-1"):
                    def backspace():
                        if sentence_queue:
                            sentence_queue.pop()
                            refresh_sentence_bar()
                    
                    def clear():
                        sentence_queue.clear()
                        refresh_sentence_bar()

                    # Play Logic
                    # Extract texts
                    texts = [(item.get("tts_text") or item["label"]).replace('"', '\\"').replace("'", "\\'") for item in sentence_queue]
                    js_array = "[" + ",".join([f'"{t}"' for t in texts]) + "]"
                    
                    play_js = f'''
                        (e) => {{
                            const texts = {js_array};
                            window.speechSynthesis.cancel();
                            window.speechSynthesis.resume(); // Ensure audio context is awake (iOS)
                            
                            let index = 0;
                            function speakNext() {{
                                if (index < texts.length) {{
                                    const u = new SpeechSynthesisUtterance(texts[index]);
                                    u.rate = 1.3; // Increased speed
                                    u.pitch = 1.0;
                                    u.volume = 1.0;
                                    u.onend = () => {{ index++; speakNext(); }};
                                    window.speechSynthesis.speak(u);
                                }}
                            }}
                            speakNext();
                        }}
                    '''
                    
                    ui.button(icon="backspace", on_click=backspace).props("flat dense color=orange").tooltip("Backspace")
                    ui.button(icon="delete", on_click=clear).props("flat dense color=red").tooltip("Clear All")
                    ui.button(icon="play_arrow", on_click=None).props("round color=green icon-size=lg").on("click", js_handler=play_js)


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
                 ui.space()
                 ui.button("Recycle Bin", icon="delete", on_click=open_recycle_bin).props("flat color=grey")

        for cat in categories:
            # Visibility Check (Category)
            is_cat_visible = cat.get("visible", True)
            if not is_cat_visible and not is_admin_mode["value"]:
                continue

            # Category Opacity
            cat_opacity = "opacity-50" if not is_cat_visible else ""
        
            with ui.column().classes(f"w-full mb-8 {cat_opacity}"):
                # Category Header
                with ui.row().classes("w-full items-center justify-between mt-4 mb-2 border-b-2 border-blue-100"):
                    ui.label(cat["name"]).classes("text-xl font-bold text-blue-800")
                    
                    if is_admin_mode["value"]:
                        def toggle_cat_vis(c_id=cat["id"]):
                            toggle_category_visibility(c_id)
                            refresh_grid()

                        def rename_cat(c_id=cat["id"], c_name=cat["name"]):
                            with ui.dialog() as d, ui.card():
                                ui.label(f"Rename Category '{c_name}'").classes("font-bold text-lg")
                                new_name_input = ui.input("New Name", value=c_name).classes("w-full")
                                
                                def save():
                                    if new_name_input.value:
                                        if rename_category(c_id, new_name_input.value):
                                            ui.notify(f"Renamed to {new_name_input.value}")
                                            d.close()
                                            refresh_grid()
                                        else:
                                            ui.notify("Error renaming (name exists?)", color="red")
                                
                                ui.button("Save", on_click=save).classes("mt-4 w-full")
                            d.open()

                        def delete_cat(c_id=cat["id"], c_name=cat["name"]):
                             with ui.dialog() as d, ui.card():
                                 ui.label(f"Delete Category '{c_name}'?").classes("font-bold text-lg")
                                 ui.label(" All items in this category will be moved to the Recycle Bin.").classes("text-sm text-gray-600")
                                 with ui.row().classes("w-full justify-end mt-4 gap-2"):
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

                # Items Row (Flex wrap)
                items = get_items(cat["id"])
                
                # Item Filter
                visible_items = [i for i in items if i.get("visible", True) or is_admin_mode["value"]]

                with ui.row().classes("w-full flex-wrap gap-2"):
                    for item in visible_items:
                        make_item_button(item)
                    
                    if not visible_items:
                        ui.label("No items.").classes("text-gray-400 italic text-sm ml-2")
        

def refresh_sentence_bar():
    render_sentence_bar()

def refresh_grid():
    render_grid()

def refresh_ui():
    """Build the single-page vertical layout."""
    global sentence_bar_container, grid_container
    
    if main_column:
        main_column.clear()
        
        with main_column.classes("p-0 gap-0")   :
            # Main Header
            with ui.row().classes("w-full items-center justify-between"):
                ui.label("Dexter Speaks").classes("text-3xl font-extrabold text-blue-900").on('click', refresh_ui)
                with ui.row().classes("items-center gap-2"):
                    # Sentence Mode Toggle
                    def toggle_sm(e):
                        is_sentence_mode["value"] = e.value
                        refresh_ui()
                    ui.switch(text="Build", value=is_sentence_mode["value"], on_change=toggle_sm).props("color=green icon=record_voice_over")
                    
                    # Admin Toggle
                    ui.switch(value=is_admin_mode["value"], on_change=toggle_admin).props("color=red icon=settings").tooltip("Admin Mode")
            
            # Sentence Bar
            sentence_bar_container = ui.column().classes("w-full sticky top-0 z-50 p-0")
            render_sentence_bar()
            
            # Main Grid
            grid_container = ui.column().classes("w-full p-0 gap-0")
            render_grid()

def toggle_admin(e):
    if is_admin_mode.get("locking", False):
        return

    if e.value:
        # Turning ON -> Require PIN
        is_admin_mode["locking"] = True # Prevent recursion
        e.sender.value = False # Visually revert immediately
        is_admin_mode["locking"] = False
        
        def on_success():
            is_admin_mode["locking"] = True
            e.sender.value = True # Set switch to ON
            is_admin_mode["value"] = True
            is_admin_mode["locking"] = False
            refresh_ui()
            
        open_pin_dialog(on_success)
            
    else:
        # Turning OFF -> Allow immediately
        is_admin_mode["value"] = False
        refresh_ui()
        #ui.notify("Admin Mode Disabled")


# --------------------------------------------------
# Layout Setup
# --------------------------------------------------

with ui.column().classes("w-full max-w-screen-xl mx-auto p-4") as main_column:
    pass 

refresh_ui()
ui.run(title="Dxtr AAC", favicon="🗣️", port=8085)
