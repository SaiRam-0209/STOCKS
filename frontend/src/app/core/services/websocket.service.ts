import { Injectable } from '@angular/core';
import { Subject, Observable } from 'rxjs';
import { AuthService } from './auth.service';

@Injectable({ providedIn: 'root' })
export class WebSocketService {
  private client: any;
  private messageSubject = new Subject<any>();
  private connected = false;

  constructor(private authService: AuthService) {}

  connect(): void {
    if (this.connected) return;

    const token = this.authService.getToken();
    if (!token) return;

    try {
      const SockJS = (window as any).SockJS || require('sockjs-client');
      const Stomp = require('@stomp/stompjs').Client;

      this.client = new Stomp({
        webSocketFactory: () => new SockJS(`${location.origin}/api/ws`),
        connectHeaders: { Authorization: `Bearer ${token}` },
        onConnect: () => {
          this.connected = true;
          const user = this.authService.getCurrentUser();
          if (user) {
            this.client.subscribe(`/user/${user.email}/queue/notifications`, (msg: any) => {
              this.messageSubject.next({ type: 'notification', data: msg.body });
            });
          }
        },
        onDisconnect: () => { this.connected = false; },
        reconnectDelay: 5000
      });

      this.client.activate();
    } catch (e) {
      console.warn('WebSocket connection failed:', e);
    }
  }

  disconnect(): void {
    if (this.client && this.connected) {
      this.client.deactivate();
      this.connected = false;
    }
  }

  getMessages(): Observable<any> {
    return this.messageSubject.asObservable();
  }
}
