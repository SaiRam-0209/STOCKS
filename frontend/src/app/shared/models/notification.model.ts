export type NotificationType =
  | 'TICKET_CREATED' | 'TICKET_UPDATED' | 'TICKET_ASSIGNED'
  | 'TICKET_RESOLVED' | 'NEW_MESSAGE' | 'AI_RESPONSE' | 'SYSTEM' | 'PASSWORD_RESET';

export interface Notification {
  id: number;
  title: string;
  message: string;
  type: NotificationType;
  isRead: boolean;
  ticketId?: number;
  ticketNumber?: string;
  createdAt: string;
}

export interface ApiResponse<T> {
  success: boolean;
  message: string;
  data: T;
  timestamp: string;
}

export interface PageResponse<T> {
  content: T[];
  totalElements: number;
  totalPages: number;
  size: number;
  number: number;
  first: boolean;
  last: boolean;
}

export interface Analytics {
  totalTickets: number;
  openTickets: number;
  inProgressTickets: number;
  resolvedTickets: number;
  closedTickets: number;
  pendingTickets: number;
  totalUsers: number;
  activeUsers: number;
  newTicketsToday: number;
  newTicketsThisWeek: number;
  newTicketsThisMonth: number;
  averageResolutionTimeHours?: number;
  pendingAIResponses: number;
  approvedAIResponses: number;
  rejectedAIResponses: number;
  ticketsByStatus: Record<string, number>;
  ticketsByPriority: Record<string, number>;
  ticketsByCategory: Record<string, number>;
  ticketsTrend: Array<{ date: string; count: number }>;
  resolutionRate: number;
  aiApprovalRate: number;
}

export interface AuditLog {
  id: number;
  userId?: number;
  userName: string;
  action: string;
  entityType?: string;
  entityId?: number;
  details?: string;
  ipAddress?: string;
  createdAt: string;
}
