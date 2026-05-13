import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { Ticket, TicketCreateRequest, TicketFilters, TicketUpdateRequest, ChatMessage, AIResponse } from '../../shared/models/ticket.model';
import { ApiResponse, PageResponse } from '../../shared/models/notification.model';

@Injectable({ providedIn: 'root' })
export class TicketService {
  private readonly API = environment.apiUrl;

  constructor(private http: HttpClient) {}

  createTicket(data: TicketCreateRequest, files?: File[]): Observable<ApiResponse<Ticket>> {
    const formData = new FormData();
    formData.append('ticket', new Blob([JSON.stringify(data)], { type: 'application/json' }));
    if (files) {
      files.forEach(file => formData.append('files', file));
    }
    return this.http.post<ApiResponse<Ticket>>(`${this.API}/tickets`, formData);
  }

  getMyTickets(filters: TicketFilters): Observable<ApiResponse<PageResponse<Ticket>>> {
    let params = new HttpParams()
      .set('page', filters.page.toString())
      .set('size', filters.size.toString())
      .set('sortBy', filters.sortBy)
      .set('sortDir', filters.sortDir);
    if (filters.search) params = params.set('search', filters.search);
    if (filters.status) params = params.set('status', filters.status);
    if (filters.priority) params = params.set('priority', filters.priority);
    if (filters.category) params = params.set('category', filters.category);
    return this.http.get<ApiResponse<PageResponse<Ticket>>>(`${this.API}/tickets`, { params });
  }

  getTicketById(id: number): Observable<ApiResponse<Ticket>> {
    return this.http.get<ApiResponse<Ticket>>(`${this.API}/tickets/${id}`);
  }

  getMessages(ticketId: number): Observable<ApiResponse<ChatMessage[]>> {
    return this.http.get<ApiResponse<ChatMessage[]>>(`${this.API}/tickets/${ticketId}/messages`);
  }

  sendMessage(ticketId: number, message: string): Observable<ApiResponse<ChatMessage>> {
    return this.http.post<ApiResponse<ChatMessage>>(`${this.API}/tickets/${ticketId}/messages`, { message });
  }

  downloadAttachment(attachmentId: number): Observable<Blob> {
    return this.http.get(`${this.API}/tickets/attachments/${attachmentId}/download`,
      { responseType: 'blob' });
  }

  // Admin endpoints
  getAllTickets(filters: TicketFilters): Observable<ApiResponse<PageResponse<Ticket>>> {
    let params = new HttpParams()
      .set('page', filters.page.toString())
      .set('size', filters.size.toString())
      .set('sortBy', filters.sortBy)
      .set('sortDir', filters.sortDir);
    if (filters.search) params = params.set('search', filters.search);
    if (filters.status) params = params.set('status', filters.status);
    if (filters.priority) params = params.set('priority', filters.priority);
    if (filters.category) params = params.set('category', filters.category);
    if (filters.userId) params = params.set('userId', filters.userId.toString());
    return this.http.get<ApiResponse<PageResponse<Ticket>>>(`${this.API}/admin/tickets`, { params });
  }

  updateTicketStatus(id: number, data: TicketUpdateRequest): Observable<ApiResponse<Ticket>> {
    return this.http.put<ApiResponse<Ticket>>(`${this.API}/admin/tickets/${id}/status`, data);
  }

  getPendingAIResponses(page = 0, size = 10): Observable<ApiResponse<PageResponse<AIResponse>>> {
    const params = new HttpParams().set('page', page).set('size', size);
    return this.http.get<ApiResponse<PageResponse<AIResponse>>>(`${this.API}/admin/ai-responses/pending`, { params });
  }

  reviewAIResponse(id: number, status: string, rejectionReason?: string): Observable<ApiResponse<AIResponse>> {
    return this.http.put<ApiResponse<AIResponse>>(`${this.API}/admin/ai-responses/${id}/review`,
      { status, rejectionReason });
  }

  exportCSV(status?: string, priority?: string, category?: string): Observable<Blob> {
    let params = new HttpParams();
    if (status) params = params.set('status', status);
    if (priority) params = params.set('priority', priority);
    if (category) params = params.set('category', category);
    return this.http.get(`${this.API}/admin/reports/tickets/csv`, { params, responseType: 'blob' });
  }

  exportPDF(status?: string, priority?: string, category?: string): Observable<Blob> {
    let params = new HttpParams();
    if (status) params = params.set('status', status);
    if (priority) params = params.set('priority', priority);
    if (category) params = params.set('category', category);
    return this.http.get(`${this.API}/admin/reports/tickets/pdf`, { params, responseType: 'blob' });
  }
}
