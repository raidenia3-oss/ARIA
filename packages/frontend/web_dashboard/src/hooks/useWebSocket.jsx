export default class WebSocketManager {
  constructor(url) {
    this.url = url
    this.ws = null
  }

  connect() {
    if (!this.url) return
    try {
      this.ws = new WebSocket(this.url)
      this.ws.onopen = () => console.log('[WS] connected', this.url)
      this.ws.onmessage = (event) => console.log('[WS] message', event.data)
      this.ws.onerror = (err) => console.error('[WS] error', err)
      this.ws.onclose = () => console.log('[WS] closed', this.url)
    } catch (e) {
      console.error('[WS] connect failed', e)
    }
  }

  send(data) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data))
    }
  }

  close() {
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }
}
