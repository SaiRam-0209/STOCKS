import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { User } from '../../shared/models/user.model';
import { ApiResponse, PageResponse } from '../../shared/models/notification.model';

@Injectable({ providedIn: 'root' })
export class UserService {
  private readonly API = environment.apiUrl;

  constructor(private http: HttpClient) {}

  getProfile(): Observable<ApiResponse<User>> {
    return this.http.get<ApiResponse<User>>(`${this.API}/users/profile`);
  }

  updateProfile(data: { name: string; phone?: string; department?: string }): Observable<ApiResponse<User>> {
    return this.http.put<ApiResponse<User>>(`${this.API}/users/profile`, data);
  }

  changePassword(data: {
    currentPassword: string; newPassword: string; confirmPassword: string;
  }): Observable<ApiResponse<void>> {
    return this.http.put<ApiResponse<void>>(`${this.API}/users/change-password`, data);
  }

  // Admin endpoints
  getAllUsers(search?: string, role?: string, isActive?: boolean, page = 0, size = 10): Observable<ApiResponse<PageResponse<User>>> {
    let params = new HttpParams().set('page', page).set('size', size);
    if (search) params = params.set('search', search);
    if (role) params = params.set('role', role);
    if (isActive !== undefined) params = params.set('isActive', isActive.toString());
    return this.http.get<ApiResponse<PageResponse<User>>>(`${this.API}/admin/users`, { params });
  }

  getUserById(id: number): Observable<ApiResponse<User>> {
    return this.http.get<ApiResponse<User>>(`${this.API}/admin/users/${id}`);
  }

  createUser(data: any): Observable<ApiResponse<User>> {
    return this.http.post<ApiResponse<User>>(`${this.API}/admin/users`, data);
  }

  toggleUserStatus(id: number): Observable<ApiResponse<User>> {
    return this.http.put<ApiResponse<User>>(`${this.API}/admin/users/${id}/toggle-status`, {});
  }

  deleteUser(id: number): Observable<ApiResponse<void>> {
    return this.http.delete<ApiResponse<void>>(`${this.API}/admin/users/${id}`);
  }
}
