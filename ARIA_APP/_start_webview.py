import webview
window = webview.create_window(
    title="ARIA OS v2.0",
    url="http://localhost:8000",
    width=1280, height=800,
    resizable=True, fullscreen=False,
    frameless=False, easy_drag=True,
    background_color="#050816",
)
webview.start(debug=False, gui="edgechromium")
