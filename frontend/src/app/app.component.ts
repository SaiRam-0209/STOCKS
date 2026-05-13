import { Component, OnInit, OnDestroy } from '@angular/core';
import { Router, NavigationEnd } from '@angular/router';
import { filter } from 'rxjs/operators';
import { Subscription } from 'rxjs';
import { AuthService } from './core/services/auth.service';
import { WebSocketService } from './core/services/websocket.service';
import { NotificationService } from './core/services/notification.service';

@Component({
  selector: 'app-root',
  template: '<router-outlet></router-outlet>'
})
export class AppComponent implements OnInit, OnDestroy {
  private sub = new Subscription();

  constructor(
    private authService: AuthService,
    private wsService: WebSocketService,
    private notificationService: NotificationService,
    private router: Router
  ) {}

  ngOnInit(): void {
    if (this.authService.isLoggedIn()) {
      this.wsService.connect();
      this.notificationService.loadUnreadCount();
    }

    this.sub.add(
      this.authService.currentUser$.subscribe(user => {
        if (user) {
          this.wsService.connect();
          this.notificationService.loadUnreadCount();
          this.router.navigate([user.role === 'ADMIN' ? '/admin/dashboard' : '/user/dashboard']);
        }
      })
    );
  }

  ngOnDestroy(): void {
    this.wsService.disconnect();
    this.sub.unsubscribe();
  }
}
