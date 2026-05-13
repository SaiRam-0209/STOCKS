import { Component, Input, Output, EventEmitter, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { NotificationService } from '../../../core/services/notification.service';
import { AuthService } from '../../../core/services/auth.service';
import { Notification } from '../../models/notification.model';

@Component({
  selector: 'app-header',
  templateUrl: './header.component.html',
  styleUrls: ['./header.component.scss']
})
export class HeaderComponent implements OnInit {
  @Input() title = 'Dashboard';
  @Output() menuToggle = new EventEmitter<void>();

  unreadCount = 0;
  notifications: Notification[] = [];
  isAdmin = false;

  constructor(
    private notificationService: NotificationService,
    private authService: AuthService,
    private router: Router
  ) {}

  ngOnInit(): void {
    this.isAdmin = this.authService.isAdmin();
    this.notificationService.unreadCount$.subscribe(count => this.unreadCount = count);
    this.loadNotifications();
  }

  loadNotifications(): void {
    this.notificationService.getNotifications(0, 10).subscribe(res => {
      if (res.success) {
        this.notifications = res.data.content;
      }
    });
  }

  markAllRead(): void {
    this.notificationService.markAllAsRead().subscribe(() => {
      this.notifications.forEach(n => n.isRead = true);
      this.notificationService.unreadCount$.next(0);
    });
  }

  onNotificationClick(n: Notification): void {
    if (!n.isRead) {
      this.notificationService.markAsRead(n.id).subscribe(() => {
        n.isRead = true;
        if (this.unreadCount > 0) {
          this.notificationService.unreadCount$.next(this.unreadCount - 1);
        }
      });
    }
    if (n.ticketId) {
      const route = this.isAdmin ? `/admin/tickets/${n.ticketId}` : `/user/tickets/${n.ticketId}`;
      this.router.navigate([route]);
    }
  }

  getNotificationIcon(type: string): string {
    const icons: Record<string, string> = {
      'TICKET_CREATED': 'add_circle',
      'TICKET_UPDATED': 'update',
      'TICKET_ASSIGNED': 'assignment',
      'TICKET_RESOLVED': 'check_circle',
      'NEW_MESSAGE': 'chat',
      'AI_RESPONSE': 'smart_toy',
      'SYSTEM': 'notifications',
      'PASSWORD_RESET': 'lock_reset'
    };
    return icons[type] || 'notifications';
  }

  formatTime(dateStr: string): string {
    const date = new Date(dateStr);
    const now = new Date();
    const diff = (now.getTime() - date.getTime()) / 1000;
    if (diff < 60) return 'Just now';
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
  }
}
