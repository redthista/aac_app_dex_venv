import os
import shutil
import yaml
from pathlib import Path
from datetime import datetime
from PIL import Image
import io
import uuid

# ==================================================
# Configuration
# ==================================================

DATA_DIR = Path(os.getenv("AAC_DATA_DIR", "data"))
TRASH_DIR = DATA_DIR / "Trash"
LOG_FILE = DATA_DIR / "usage.log"
CONFIG_FILE = DATA_DIR / "config.yaml"
MAX_IMAGE_SIZE = (800, 800)

# ==================================================
# Helpers
# ==================================================

def ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    TRASH_DIR.mkdir(parents=True, exist_ok=True)
    
    # Ensure config file exists with defaults
    if not CONFIG_FILE.exists():
        default_config = {
            "pin": "1234",
            "categories": {}
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            yaml.dump(default_config, f, default_flow_style=False)

def read_config():
    """Read the centralized config file."""
    ensure_data_dir()
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {"pin": "1234", "categories": {}}
    except:
        return {"pin": "1234", "categories": {}}

def write_config(config):
    """Write the centralized config file."""
    ensure_data_dir()
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

def safe_filename(name):
    """Make a string safe for filesystem."""
    return "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).strip()

def process_and_save_image(image_data: bytes, dest_path: Path):
    """
    Resize and save image data to destination.
    Converts to efficient format (WebP or JPEG).
    """
    try:
        img = Image.open(io.BytesIO(image_data))
        
        # Resize if too big
        img.thumbnail(MAX_IMAGE_SIZE, Image.Resampling.LANCZOS)
        
        if img.mode == 'RGBA':
            # Save as PNG to keep transparency
            dest_path = dest_path.with_suffix('.png')
            img.save(dest_path, format="PNG", optimize=True)
        else:
            # Save as JPEG
            dest_path = dest_path.with_suffix('.jpg')
            img = img.convert('RGB')
            img.save(dest_path, format="JPEG", quality=85)
            
        return dest_path.name
    except Exception as e:
        print(f"Image processing error: {e}")
        import traceback
        traceback.print_exc()
        return None

# ==================================================
# Category Operations
# ==================================================

def get_categories():
    """
    Return list of dicts: {'id': 'Name', 'name': 'Name', 'order': int} 
    'id' is the folder name.
    Sorted by order field (lower numbers first), then alphabetically.
    """
    ensure_data_dir()
    config = read_config()
    cat_configs = config.get("categories", {})
    
    cats = []
    if DATA_DIR.exists():
        for entry in os.scandir(DATA_DIR):
            if entry.is_dir() and entry.name != "Trash":
                cat_id = entry.name
                cat_config = cat_configs.get(cat_id, {"visible": True, "order": 999})
                
                cats.append({
                    "id": cat_id,
                    "name": cat_id,
                    "visible": cat_config.get("visible", True),
                    "order": cat_config.get("order", 999)
                })
    cats.sort(key=lambda x: (x["order"], x["name"]))
    return cats

def toggle_category_visibility(category_id):
    ensure_data_dir()
    cat_path = DATA_DIR / category_id
    if not cat_path.exists():
        return False
    
    config = read_config()
    if "categories" not in config:
        config["categories"] = {}
    if category_id not in config["categories"]:
        config["categories"][category_id] = {"visible": True, "order": 999}
    
    current_visible = config["categories"][category_id].get("visible", True)
    config["categories"][category_id]["visible"] = not current_visible
    
    write_config(config)
    return config["categories"][category_id]["visible"]

def create_category(name):
    ensure_data_dir()
    safe_name = safe_filename(name)
    if not safe_name:
        return None
    
    cat_path = DATA_DIR / safe_name
    cat_path.mkdir(exist_ok=True)
    return safe_name

def rename_category(old_id, new_name):
    """
    Rename category folder and update all internal item references.
    """
    ensure_data_dir()
    safe_new_id = safe_filename(new_name)
    if not safe_new_id:
        return False
        
    old_path = DATA_DIR / old_id
    new_path = DATA_DIR / safe_new_id
    
    if not old_path.exists():
        return False
        
    if new_path.exists() and new_path != old_path:
        return False # Target exists
        
    # Rename Folder
    try:
        os.rename(old_path, new_path)
    except Exception as e:
        print(f"Error renaming folder: {e}")
        return False
        
    # Update all items inside to have new cat_id
    for entry in os.scandir(new_path):
        if entry.is_file() and entry.name.endswith(".yaml"):
            try:
                # Read
                with open(entry.path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                
                # Update
                data["cat_id"] = safe_new_id
                
                # Write
                with open(entry.path, "w", encoding="utf-8") as f:
                    yaml.dump(data, f)
            except Exception as e:
                print(f"Error updating item {entry.name}: {e}")
                
    return True

def delete_category(category_id):
    """
    Soft delete all items in category, then remove the folder.
    """
    ensure_data_dir()
    cat_path = DATA_DIR / category_id
    if not cat_path.exists():
        return False
    
    # Soft delete all items
    # Note: get_items and soft_delete_item are defined below, but Python runtime resolution handles this.
    items = get_items(category_id)
    for item in items:
        soft_delete_item(category_id, item["id"])
        
    try:
        shutil.rmtree(cat_path)
        return True
    except Exception as e:
        print(f"Error deleting category {category_id}: {e}")
        return False

def move_category_up(category_id):
    """
    Move category up in the display order (decrease order number).
    Swap order with the category above it.
    """
    ensure_data_dir()
    categories = get_categories()
    
    # Find current category index
    current_idx = None
    for idx, cat in enumerate(categories):
        if cat["id"] == category_id:
            current_idx = idx
            break
    
    if current_idx is None or current_idx == 0:
        return False  # Already at top or not found
    
    # Swap order with previous category
    current_cat = categories[current_idx]
    prev_cat = categories[current_idx - 1]
    
    # Update order values
    _set_category_order(current_cat["id"], prev_cat["order"])
    _set_category_order(prev_cat["id"], current_cat["order"])
    
    return True

def move_category_down(category_id):
    """
    Move category down in the display order (increase order number).
    Swap order with the category below it.
    """
    ensure_data_dir()
    categories = get_categories()
    
    # Find current category index
    current_idx = None
    for idx, cat in enumerate(categories):
        if cat["id"] == category_id:
            current_idx = idx
            break
    
    if current_idx is None or current_idx >= len(categories) - 1:
        return False  # Already at bottom or not found
    
    # Swap order with next category
    current_cat = categories[current_idx]
    next_cat = categories[current_idx + 1]
    
    # Update order values
    _set_category_order(current_cat["id"], next_cat["order"])
    _set_category_order(next_cat["id"], current_cat["order"])
    
    return True

def _set_category_order(category_id, order):
    """
    Internal helper to set the order field in config.yaml.
    """
    ensure_data_dir()
    cat_path = DATA_DIR / category_id
    if not cat_path.exists():
        return False
    
    config = read_config()
    if "categories" not in config:
        config["categories"] = {}
    if category_id not in config["categories"]:
        config["categories"][category_id] = {"visible": True, "order": 999}
    
    config["categories"][category_id]["order"] = order
    write_config(config)
    return True

# ==================================================
# Item Operations
# ==================================================

def get_items(category_id):
    """
    Scan category folder for .yaml files.
    """
    if not category_id:
        return []
    
    cat_path = DATA_DIR / category_id
    if not cat_path.exists():
        return []

    items = []
    for entry in os.scandir(cat_path):
        if entry.is_file() and entry.name.endswith(".yaml"):
            try:
                with open(entry.path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                
                stem = Path(entry.name).stem
                
                item = {
                    "id": stem,
                    "cat_id": category_id,
                    "label": data.get("label", stem),
                    "tts_text": data.get("tts_text", data.get("label", stem)),
                    "image_path": data.get("image_path", None),
                    "color": data.get("color", "blue"),
                    "visible": data.get("visible", True)
                }
                
                if not item["image_path"]:
                    for ext in [".png", ".jpg", ".jpeg", ".gif", ".webp"]:
                        img_candidate = cat_path / (stem + ext)
                        if img_candidate.exists():
                            item["image_path"] = str(img_candidate.absolute())
                            break
                            
                items.append(item)
            except Exception as e:
                print(f"Error loading {entry.name}: {e}")

    items.sort(key=lambda x: x["label"])
    return items

def toggle_item_visibility(category_id, item_id):
    cat_path = DATA_DIR / category_id
    yaml_path = cat_path / f"{item_id}.yaml"
    
    if not yaml_path.exists():
        return False
        
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
        
    current = data.get("visible", True)
    data["visible"] = not current
    
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f)
        
    return data["visible"]

def create_item(category_id, label, image_file=None, image_url=None, tts_text=None, color=None):
    cat_path = DATA_DIR / category_id
    if not cat_path.exists():
        return None

    file_stem = str(uuid.uuid4())
    yaml_path = cat_path / f"{file_stem}.yaml"
    
    data = {
        "label": label,
        "created_at": str(datetime.now()),
        "visible": True
    }
    if tts_text:
        data["tts_text"] = tts_text
    if color:
        data["color"] = color

    if image_file:
        dest_path = cat_path / file_stem 
        saved_name = process_and_save_image(image_file, dest_path)
    elif image_url:
        data["image_path"] = image_url

    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f)
    
    return file_stem

def update_item(category_id, item_id, **kwargs):
    cat_path = DATA_DIR / category_id
    yaml_path = cat_path / f"{item_id}.yaml"
    
    if not yaml_path.exists():
        return
        
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    
    if "new_label" in kwargs:
        data["label"] = kwargs["new_label"]
    if "new_tts_text" in kwargs:
        data["tts_text"] = kwargs["new_tts_text"]
    if "new_color" in kwargs:
        data["color"] = kwargs["new_color"]
    if "new_visible" in kwargs:
        data["visible"] = kwargs["new_visible"]

    if "new_image_file" in kwargs and kwargs["new_image_file"]:
        # Delete old images first
        for ext in [".png", ".jpg", ".jpeg", ".gif", ".webp"]:
            old_img = cat_path / f"{item_id}{ext}"
            if old_img.exists():
                os.remove(old_img)
                
        # Process and save new image
        dest_path = cat_path / item_id
        saved_filename = process_and_save_image(kwargs["new_image_file"], dest_path)
        
        # Only remove image_path from YAML if new image was successfully saved
        # The get_items function will auto-detect the image file
        if saved_filename and "image_path" in data:
            del data["image_path"]

    elif "new_image_url" in kwargs and kwargs["new_image_url"]:
         data["image_path"] = kwargs["new_image_url"]

    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f)
        
    # Handle Category Move
    if "new_category_id" in kwargs and kwargs["new_category_id"]:
        new_cat = kwargs["new_category_id"]
        if new_cat != category_id:
            new_cat_path = DATA_DIR / new_cat
            if new_cat_path.exists():
                # Move YAML
                new_yaml_path = new_cat_path / f"{item_id}.yaml"
                shutil.move(yaml_path, new_yaml_path)
                
                # Move Image(s)
                for ext in [".png", ".jpg", ".jpeg", ".gif", ".webp"]:
                     old_img = cat_path / f"{item_id}{ext}"
                     if old_img.exists():
                         shutil.move(old_img, new_cat_path / f"{item_id}{ext}")


def delete_item(category_id, item_id):
    """Hard delete item."""
    cat_path = DATA_DIR / category_id
    yaml_path = cat_path / f"{item_id}.yaml"
    if yaml_path.exists():
        os.remove(yaml_path)
    
    for ext in [".png", ".jpg", ".jpeg", ".gif", ".webp"]:
        img_path = cat_path / f"{item_id}{ext}"
        if img_path.exists():
            os.remove(img_path)

# ==================================================
# Recycle Bin Operations
# ==================================================

def soft_delete_item(category_id, item_id):
    """Move item to Trash with metadata about origin."""
    ensure_data_dir()
    
    source_cat_path = DATA_DIR / category_id
    source_yaml = source_cat_path / f"{item_id}.yaml"
    
    if not source_yaml.exists():
        return
    
    # Update metadata with original category
    with open(source_yaml, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    
    data["original_category"] = category_id
    data["deleted_at"] = str(datetime.now())
    
    with open(source_yaml, "w", encoding="utf-8") as f:
        yaml.dump(data, f)
        
    # Move YAML
    dest_yaml = TRASH_DIR / f"{item_id}.yaml"
    # Handle collision in trash? For now, overwrite or append timestamp?
    # Simple overwrite for now.
    shutil.move(source_yaml, dest_yaml)
    
    # Move Image(s)
    # We find any image with same stem
    for ext in [".png", ".jpg", ".jpeg", ".gif", ".webp"]:
        source_img = source_cat_path / f"{item_id}{ext}"
        if source_img.exists():
            dest_img = TRASH_DIR / f"{item_id}{ext}"
            shutil.move(source_img, dest_img)

def restore_item(item_id):
    """Restore item from Trash to original category."""
    ensure_data_dir()
    
    trash_yaml = TRASH_DIR / f"{item_id}.yaml"
    if not trash_yaml.exists():
        return False
        
    with open(trash_yaml, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
        
    original_cat = data.get("original_category", "Restored")
    
    # Ensure target category exists
    target_cat_path = DATA_DIR / original_cat
    if not target_cat_path.exists():
        create_category(original_cat)
        
    item_id_stem = item_id
    counter = 1
    
    # Check for collision and generate new ID if needed
    while (target_cat_path / f"{item_id_stem}.yaml").exists():
        item_id_stem = f"{item_id}_{counter}"
        counter += 1

    # Clean metadata
    if "original_category" in data:
        del data["original_category"]
    if "deleted_at" in data:
        del data["deleted_at"]
        
    with open(trash_yaml, "w", encoding="utf-8") as f:
        yaml.dump(data, f)
        
    # Move files back with potential rename
    shutil.move(trash_yaml, target_cat_path / f"{item_id_stem}.yaml")
    
    for ext in [".png", ".jpg", ".jpeg", ".gif", ".webp"]:
        trash_img = TRASH_DIR / f"{item_id}{ext}"
        if trash_img.exists():
            shutil.move(trash_img, target_cat_path / f"{item_id_stem}{ext}")
            
    return True

def permanent_delete_item(item_id):
    """Delete item from Trash forever."""
    delete_item("Trash", item_id) # Reuse delete_item pointing to Trash folder

def get_trash_items():
    """Get list of items in Trash."""
    return get_items("Trash")

def empty_trash():
    """Delete all items in Trash."""
    ensure_data_dir()
    for entry in os.scandir(TRASH_DIR):
        if entry.is_file():
            os.remove(entry.path)


# ==================================================
# Logging
# ==================================================

def log_usage(item_id):
    ensure_data_dir()
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().isoformat()},{item_id}\n")
