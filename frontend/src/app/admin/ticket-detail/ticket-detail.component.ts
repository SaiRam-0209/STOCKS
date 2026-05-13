import { Component, OnInit, ViewChild, ElementRef } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { FormBuilder, FormGroup, Validators, FormControl } from '@angular/forms';
import { MatSnackBar } from '@angular/material/snack-bar';
import { TicketService } from '../../core/services/ticket.service';
import { UserService } from '../../core/services/user.service';
import { Ticket, ChatMessage, TicketUpdateRequest } from '../../shared/models/ticket.model';
import { User } from '../../shared/models/user.model';
import { AuthService } from '../../core/services/auth.service';

@Component({
  selector: 'app-admin-ticket-detail',
  templateUrl: './ticket-detail.component.html',
  styleUrls: ['./ticket-detail.component.scss']
})
export class AdminTicketDetailComponent implements OnInit {
  pageTitle = 'Ticket Management';
  ticket: Ticket | null = null;
  loading = true;
  updating = false;
  sending = false;
  admins: User[] = [];
  msgCtrl = new FormControl('', [Validators.required, Validators.maxLength(2000)]);
  currentUserId = 0;

  updateForm: FormGroup;

  statuses = ['OPEN','IN_PROGRESS','PENDING','RESOLVED','CLOSED'];
  agentTypes = ['HUMAN', 'AI'];

  @ViewChild('chatEnd') chatEnd!: ElementRef;

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private fb: FormBuilder,
    private ticketService: TicketService,
    private userService: UserService,
    private authService: AuthService,
    private snackBar: MatSnackBar
  ) {
    this.updateForm = this.fb.group({
      status: ['', Validators.required],
      assignedToId: [''],
      assignedAgentType: [''],
      adminNote: ['', [Validators.maxLength(2000)]]
    });
  }

  ngOnInit(): void {
    this.currentUserId = this.authService.getCurrentUser()?.userId || 0;
    const id = Number(this.route.snapshot.paramMap.get('id'));
    this.loadTicket(id);
    this.loadAdmins();
  }

  loadTicket(id: number): void {
    this.ticketService.getTicketById(id).subscribe({
      next: (res) => {
        this.ticket = res.data;
        this.loading = false;
        this.updateForm.patchValue({
          status: res.data.status,
          assignedToId: res.data.assignedToId || '',
          assignedAgentType: res.data.assignedAgentType || ''
        });
      },
      error: () => { this.loading = false; }
    });
  }

  loadAdmins(): void {
    this.userService.getAllUsers(undefined, 'ADMIN', undefined, 0, 50).subscribe(res => {
      if (res.success) this.admins = res.data.content;
    });
  }

  updateTicket(): void {
    if (this.updateForm.invalid || !this.ticket) return;
    this.updating = true;
    const req: TicketUpdateRequest = {
      status: this.updateForm.value.status,
      assignedToId: this.updateForm.value.assignedToId || undefined,
      assignedAgentType: this.updateForm.value.assignedAgentType || undefined,
      adminNote: this.updateForm.value.adminNote
    };

    this.ticketService.updateTicketStatus(this.ticket.id, req).subscribe({
      next: (res) => {
        this.updating = false;
        this.ticket = res.data;
        this.updateForm.patchValue({ adminNote: '' });
        this.snackBar.open('Ticket updated successfully!', '✕', { duration: 3000, panelClass: ['snack-success'] });
      },
      error: (err) => {
        this.updating = false;
        this.snackBar.open(err.error?.message || 'Failed to update ticket.', '✕', { duration: 4000, panelClass: ['snack-error'] });
      }
    });
  }

  sendMessage(): void {
    if (!this.msgCtrl.valid || !this.ticket) return;
    const msg = this.msgCtrl.value!.trim();
    if (!msg) return;
    this.sending = true;
    this.ticketService.sendMessage(this.ticket.id, msg).subscribe({
      next: (res) => {
        this.ticket!.chatMessages = [...(this.ticket!.chatMessages || []), res.data];
        this.msgCtrl.reset();
        this.sending = false;
        setTimeout(() => this.chatEnd?.nativeElement?.scrollIntoView({ behavior: 'smooth' }), 100);
      },
      error: () => { this.sending = false; }
    });
  }

  reviewAIResponse(id: number, status: string): void {
    this.ticketService.reviewAIResponse(id, status).subscribe({
      next: () => {
        if (this.ticket?.aiResponses) {
          const ai = this.ticket.aiResponses.find(r => r.id === id);
          if (ai) ai.status = status as any;
        }
        this.snackBar.open(`AI response ${status.toLowerCase()}d!`, '✕', { duration: 3000, panelClass: ['snack-success'] });
      }
    });
  }

  getMsgClass(msg: ChatMessage): string {
    if (msg.messageType === 'STATUS_UPDATE' || msg.messageType === 'SYSTEM') return 'chat-bubble--system';
    if (msg.isAiGenerated) return 'chat-bubble--ai';
    if (msg.senderId === this.currentUserId) return 'chat-bubble--user';
    return 'chat-bubble--admin';
  }

  isOwnMessage(msg: ChatMessage): boolean { return msg.senderId === this.currentUserId; }

  getStatusClass(s: string): string {
    const m: Record<string, string> = { OPEN: 'badge--open', IN_PROGRESS: 'badge--in-progress', PENDING: 'badge--pending', RESOLVED: 'badge--resolved', CLOSED: 'badge--closed' };
    return 'badge ' + (m[s] || '');
  }

  getPriorityClass(p: string): string {
    const m: Record<string, string> = { LOW: 'badge--low', MEDIUM: 'badge--medium', HIGH: 'badge--high', CRITICAL: 'badge--critical' };
    return 'badge ' + (m[p] || '');
  }

  formatDate(d: string): string {
    return new Date(d).toLocaleString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  }

  formatTime(d: string): string { return new Date(d).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }); }
}
