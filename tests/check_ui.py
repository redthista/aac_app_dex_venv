from nicegui import ui
print(dir(ui))
try:
    print(ui.open)
except AttributeError:
    print("ui.open missing")

try:
    print(ui.navigate.to)
except AttributeError:
    print("ui.navigate missing")
