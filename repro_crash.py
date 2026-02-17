from nicegui import ui

def test():
    with ui.card():
        ui.label("Test").classes("text-sm font-bold text-center leading-tight w-full overflow-hidden text-ellipsis px-1 pb-1")

ui.button("Click me", on_click=test)

# Run in a way that just builds it
test()
print("Success")
