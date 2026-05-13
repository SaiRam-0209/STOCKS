import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { Analytics, ApiResponse, AuditLog, PageResponse } from '../../shared/models/notification.model';

@Injectable({ providedIn: 'root' })
export class AnalyticsService {
  private readonly API = environment.apiUrl;

  constructor(private http: HttpClient) {}

  getAnalytics(): Observable<ApiResponse<Analytics>> {
    return this.http.get<ApiResponse<Analytics>>(`${this.API}/admin/analytics`);
  }

  getAuditLogs(search?: string, userId?: number, page = 0, size = 20): Observable<ApiResponse<PageResponse<AuditLog>>> {
    let url = `${this.API}/admin/audit-logs?page=${page}&size=${size}`;
    if (search) url += `&search=${encodeURIComponent(search)}`;
    if (userId) url += `&userId=${userId}`;
    return this.http.get<ApiResponse<PageResponse<AuditLog>>>(url);
  }
}
