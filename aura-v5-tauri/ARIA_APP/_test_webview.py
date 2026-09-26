import webview
window = webview.create_window(
    title="ARIA OS Test",
    url="http://localhost:8000",
    width=800, height=600,
)
webview.start(debug=True, gui="edgechromium")
