"""
db.py
-----

SQLite database helper module for the AAC communication app.

Responsibilities:
- Create database if missing
- Provide DB connection
- Provide CRUD operations for categories and items
- Log item usage

Works both locally and inside Docker via AAC_DATA_DIR env variable.
"""

from pathlib import Path
import sqlite3
import os


# ==================================================
# Configuration
# ==================================================

# Directory can be overridden in Docker:
#   AAC_DATA_DIR=/data
DATA_DIR = Path(os.getenv("AAC_DATA_DIR", "data"))
DB_PATH = DATA_DIR / "db.sqlite"


# ==================================================
# Connection helpers
# ==================================================

def get_connection():
    """
    Create and return a SQLite connection.

    Automatically creates data folder if missing.
    Rows behave like dictionaries.

    Returns
    -------
    sqlite3.Connection
        Database connection.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ==================================================
# Database initialization
# ==================================================

def init_db():
    """
    Create database tables if they do not exist.

    Safe to call on every application startup.

    Example
    -------
    from db import init_db
    init_db()
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            icon_path TEXT,
            color TEXT,
            sort_order INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER,
            label TEXT NOT NULL,
            image_path TEXT,
            audio_path TEXT,
            color TEXT,
            is_visible INTEGER DEFAULT 1,
            sort_order INTEGER DEFAULT 0,
            FOREIGN KEY(category_id) REFERENCES categories(id)
        );

        CREATE TABLE IF NOT EXISTS usage_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)

    conn.commit()
    conn.close()


# ==================================================
# Category operations
# ==================================================

def create_category(name, icon_path=None, color=None, sort_order=0):
    """
    Create a new category.

    Parameters
    ----------
    name : str
        Display name of category.
    icon_path : str | None
        Optional icon image path.
    color : str | None
        Hex or CSS color.
    sort_order : int
        Ordering priority.

    Returns
    -------
    int
        Newly created category ID.

    Example
    -------
    cid = create_category("Food", color="#ffaa00")
    """
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO categories
           (name, icon_path, color, sort_order)
           VALUES (?, ?, ?, ?)""",
        (name, icon_path, color, sort_order),
    )
    conn.commit()
    cid = cur.lastrowid
    conn.close()
    return cid


def get_categories():
    """
    Fetch all categories ordered for display.

    Returns
    -------
    list[sqlite3.Row]
        Category records.
    """
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM categories ORDER BY sort_order, name"
    ).fetchall()
    conn.close()
    return rows


def update_category(category_id, **fields):
    """
    Update category fields.

    Parameters
    ----------
    category_id : int
        Category ID.
    **fields :
        Columns to update.

    Example
    -------
    update_category(1, name="Meals", color="#ff0000")
    """
    keys = ", ".join(f"{k}=?" for k in fields)
    values = list(fields.values())
    values.append(category_id)

    conn = get_connection()
    conn.execute(
        f"UPDATE categories SET {keys} WHERE id=?",
        values,
    )
    conn.commit()
    conn.close()


def delete_category(category_id):
    """
    Delete a category.

    Parameters
    ----------
    category_id : int
        Category ID.
    """
    conn = get_connection()
    conn.execute("DELETE FROM categories WHERE id=?", (category_id,))
    conn.commit()
    conn.close()


# ==================================================
# Item operations
# ==================================================

def create_item(
    category_id,
    label,
    image_path=None,
    audio_path=None,
    color=None,
    sort_order=0,
    is_visible=1,
):
    """
    Create a communication item/button.

    Returns
    -------
    int
        New item ID.
    """
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO items
           (category_id, label, image_path, audio_path,
            color, sort_order, is_visible)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            category_id,
            label,
            image_path,
            audio_path,
            color,
            sort_order,
            is_visible,
        ),
    )
    conn.commit()
    iid = cur.lastrowid
    conn.close()
    return iid


def get_items(category_id=None):
    """
    Fetch items.

    Parameters
    ----------
    category_id : int | None
        If provided, filter by category.

    Returns
    -------
    list[sqlite3.Row]
        Item records.
    """
    conn = get_connection()

    if category_id:
        rows = conn.execute(
            """SELECT * FROM items
               WHERE category_id=? AND is_visible=1
               ORDER BY sort_order, label""",
            (category_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM items ORDER BY sort_order, label"
        ).fetchall()

    conn.close()
    return rows


def update_item(item_id, **fields):
    """
    Update item values.

    Example
    -------
    update_item(3, label="Banana", color="#ffff00")
    """
    keys = ", ".join(f"{k}=?" for k in fields)
    values = list(fields.values())
    values.append(item_id)

    conn = get_connection()
    conn.execute(
        f"UPDATE items SET {keys} WHERE id=?",
        values,
    )
    conn.commit()
    conn.close()


def delete_item(item_id):
    """
    Delete an item.

    Parameters
    ----------
    item_id : int
        Item ID.
    """
    conn = get_connection()
    conn.execute("DELETE FROM items WHERE id=?", (item_id,))
    conn.commit()
    conn.close()


# ==================================================
# Usage logging
# ==================================================

def log_usage(item_id):
    """
    Log when a communication item is pressed.

    Parameters
    ----------
    item_id : int
        Pressed item ID.
    """
    conn = get_connection()
    conn.execute(
        "INSERT INTO usage_log (item_id) VALUES (?)",
        (item_id,),
    )
    conn.commit()
    conn.close()


# ==================================================
# CLI creation
# ==================================================

if __name__ == "__main__":
    init_db()
    print("Database ready:", DB_PATH.resolve())
