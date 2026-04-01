from nicegui import ui
import sys

attrs = dir(ui)
print(f"Attributes count: {len(attrs)}")
for a in attrs:
    if 'open' in a or 'nav' in a or 'link' in a:
        print(f"Found related: {a}")
        
try:
    print(f"Type of ui: {type(ui)}")
except:
    pass
