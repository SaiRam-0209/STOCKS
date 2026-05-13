export type TicketStatus = 'OPEN' | 'IN_PROGRESS' | 'PENDING' | 'RESOLVED' | 'CLOSED';
export type TicketPriority = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
export type TicketCategory = 'TECHNICAL' | 'BILLING' | 'GENERAL' | 'FEATURE_REQUEST' | 'BUG_REPORT' | 'ACCOUNT' | 'OTHER';
export type MessageType = 'USER_MESSAGE' | 'ADMIN_REPLY' | 'AI_RESPONSE' | 'STATUS_UPDATE' | 'SYSTEM';

export interface Ticket {
  id: number;
  ticketNumber: string;
  userId: number;
  userName: string;
  userEmail: string;
  assignedToId?: number;
  assignedToName?: string;
  category: TicketCategory;
  priority: TicketPriority;
  status: TicketStatus;
  subject: string;
  description: string;
  aiSummary?: string;
  assignedAgentType?: 'HUMAN' | 'AI';
  resolvedAt?: string;
  createdAt: string;
  updatedAt: string;
  attachments?: Attachment[];
  chatMessages?: ChatMessage[];
  aiResponses?: AIResponse[];
  messageCount: number;
}

export interface Attachment {
  id: number;
  fileName: string;
  originalName: string;
  fileSize: number;
  fileType: string;
  downloadUrl: string;
  createdAt: string;
}

export interface ChatMessage {
  id: number;
  ticketId: number;
  senderId: number;
  senderName: string;
  senderRole: string;
  message: string;
  messageType: MessageType;
  isAiGenerated: boolean;
  createdAt: string;
}

export interface AIResponse {
  id: number;
  ticketId: number;
  response: string;
  confidenceScore?: number;
  status: 'PENDING' | 'APPROVED' | 'REJECTED';
  reviewedByName?: string;
  reviewedAt?: string;
  rejectionReason?: string;
  createdAt: string;
}

export interface TicketCreateRequest {
  subject: string;
  description: string;
  category: TicketCategory;
  priority: TicketPriority;
}

export interface TicketUpdateRequest {
  status: TicketStatus;
  assignedToId?: number;
  assignedAgentType?: 'HUMAN' | 'AI';
  adminNote?: string;
}

export interface TicketFilters {
  search?: string;
  status?: TicketStatus;
  priority?: TicketPriority;
  category?: TicketCategory;
  userId?: number;
  page: number;
  size: number;
  sortBy: string;
  sortDir: 'asc' | 'desc';
}
