import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { BehaviorSubject, Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { Notification } from '../../shared/models/notification.model';
import { ApiResponse, PageResponse } from '../../shared/models/notification.model';

@Injectable({ providedIn: 'root' })
export class NotificationService {
  private readonly API = environment.apiUrl;
  unreadCount$ = new BehaviorSubject<number>(0);

  constructor(private http: HttpClient) {}

  getNotifications(page = 0, size = 20): Observable<ApiResponse<PageResponse<Notification>>> {
    return this.http.get<ApiResponse<PageResponse<Notification>>>(
      `${this.API}/users/notifications?page=${page}&size=${size}`
    );
  }

  getUnreadCount(): Observable<ApiResponse<number>> {
    return this.http.get<ApiResponse<number>>(`${this.API}/users/notifications/unread-count`);
  }

  markAsRead(id: number): Observable<ApiResponse<void>> {
    return this.http.put<ApiResponse<void>>(`${this.API}/users/notifications/${id}/read`, {});
  }

  markAllAsRead(): Observable<ApiResponse<void>> {
    return this.http.put<ApiResponse<void>>(`${this.API}/users/notifications/mark-all-read`, {});
  }

  loadUnreadCount(): void {
    this.getUnreadCount().subscribe(res => {
      if (res.success) this.unreadCount$.next(res.data);
    });
  }
}
