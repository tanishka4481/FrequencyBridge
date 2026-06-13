const WS_URL = "ws://localhost:8000/ws";

class FreqBridgeStream {
    constructor() {
        this.socket = null;
        this.listeners = [];
        this.reconnectAttempts = 0;
        this.connect();
    }

    connect() {
        this.socket = new WebSocket(WS_URL);

        this.socket.onopen = () => {
            console.log("Connected to FreqBridge Simulator");
            this.reconnectAttempts = 0;
            document.querySelector('.status-indicator').style.color = 'var(--color-success)';
        };

        this.socket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.listeners.forEach(fn => fn(data));
        };

        this.socket.onclose = () => {
            console.log("Disconnected from server.");
            document.querySelector('.status-indicator').style.color = 'var(--color-danger)';
            const delay = Math.min(1000 * (2 ** this.reconnectAttempts), 30000);
            this.reconnectAttempts++;
            setTimeout(() => this.connect(), delay);
        };

        this.socket.onerror = (err) => {
            console.error("WebSocket Error:", err);
            this.socket.close();
        };
    }

    subscribe(callback) {
        this.listeners.push(callback);
    }
}

const simStream = new FreqBridgeStream();
