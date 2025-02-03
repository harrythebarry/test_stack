import { API_URL } from '@/lib/api';

export class ProjectWebSocketService {
  constructor(chatId) {
    this.ws = null;
    this.chatId = chatId;
  }

  connect() {
    const wsUrl = API_URL;
    const wsProtocol = wsUrl.startsWith('https') ? 'wss://' : 'ws://';
    const baseUrl = wsUrl.replace(/^https?:\/\//, '');

    // Get token from localStorage
    const token = localStorage.getItem('token');
    if (!token) {
      console.error('No authentication token found');
      return;
    }

    this.ws = new WebSocket(
      `${wsProtocol}${baseUrl}/api/ws/chat/${this.chatId}?token=${token}`
    );
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  sendMessage(message) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    } else {
      console.error('WebSocket is not connected');
    }
  }
}
