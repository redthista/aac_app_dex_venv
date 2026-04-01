from nicegui import ui
try:
    print(f"ui.navigate type: {type(ui.navigate)}")
    print(dir(ui.navigate))
    if hasattr(ui.navigate, 'to'):
        print("ui.navigate.to exists")
    else:
        print("ui.navigate.to MISSING")
except Exception as e:
    print(e)
