export interface User {
  id: number;
  name: string;
  email: string;
  role: 'USER' | 'ADMIN';
  phone?: string;
  department?: string;
  profilePicture?: string;
  isActive: boolean;
  lastLogin?: string;
  createdAt: string;
  totalTickets: number;
  openTickets: number;
  resolvedTickets: number;
}

export interface AuthResponse {
  token: string;
  type: string;
  userId: number;
  name: string;
  email: string;
  role: 'USER' | 'ADMIN';
  message: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  name: string;
  email: string;
  password: string;
  confirmPassword: string;
  phone?: string;
  department?: string;
}
