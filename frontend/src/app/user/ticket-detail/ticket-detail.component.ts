import { Component, OnInit, ViewChild, ElementRef, AfterViewChecked } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { FormControl, Validators } from '@angular/forms';
import { MatSnackBar } from '@angular/material/snack-bar';
import { TicketService } from '../../core/services/ticket.service';
import { Ticket, ChatMessage, Attachment } from '../../shared/models/ticket.model';
import { AuthService } from '../../core/services/auth.service';

@Component({
  selector: 'app-ticket-detail',
  templateUrl: './ticket-detail.component.html',
  styleUrls: ['./ticket-detail.component.scss']
})
export class TicketDetailComponent implements OnInit, AfterViewChecked {
  pageTitle = 'Ticket Detail';
  ticket: Ticket | null = null;
  loading = true;
  sending = false;
  msgCtrl = new FormControl('', [Validators.required, Validators.minLength(1), Validators.maxLength(2000)]);
  currentUserId = 0;

  @ViewChild('chatEnd') chatEnd!: ElementRef;

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private ticketService: TicketService,
    private authService: AuthService,
    private snackBar: MatSnackBar
  ) {}

  ngOnInit(): void {
    this.currentUserId = this.authService.getCurrentUser()?.userId || 0;
    const id = Number(this.route.snapshot.paramMap.get('id'));
    this.loadTicket(id);
  }

  ngAfterViewChecked(): void {
    this.scrollToBottom();
  }

  loadTicket(id: number): void {
    this.ticketService.getTicketById(id).subscribe({
      next: (res) => {
        this.ticket = res.data;
        this.loading = false;
        this.pageTitle = this.ticket?.ticketNumber || 'Ticket';
      },
      error: () => { this.loading = false; this.router.navigate(['/user/tickets']); }
    });
  }

  scrollToBottom(): void {
    try { this.chatEnd?.nativeElement?.scrollIntoView({ behavior: 'smooth' }); } catch {}
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
      },
      error: (err) => {
        this.sending = false;
        this.snackBar.open(err.error?.message || 'Failed to send message.', '✕',
          { duration: 3000, panelClass: ['snack-error'] });
      }
    });
  }

  downloadAttachment(att: Attachment): void {
    this.ticketService.downloadAttachment(att.id).subscribe(blob => {
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = att.originalName;
      a.click();
      URL.revokeObjectURL(url);
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
    const m: Record<string, string> = {
      OPEN: 'badge--open', IN_PROGRESS: 'badge--in-progress',
      PENDING: 'badge--pending', RESOLVED: 'badge--resolved', CLOSED: 'badge--closed'
    };
    return 'badge ' + (m[s] || '');
  }

  getPriorityClass(p: string): string {
    const m: Record<string, string> = { LOW: 'badge--low', MEDIUM: 'badge--medium', HIGH: 'badge--high', CRITICAL: 'badge--critical' };
    return 'badge ' + (m[p] || '');
  }

  formatDate(d: string): string {
    return new Date(d).toLocaleString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  }

  formatTime(d: string): string {
    return new Date(d).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
  }

  formatFileSize(bytes: number): string {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / 1048576).toFixed(1) + ' MB';
  }

  get isClosed(): boolean { return this.ticket?.status === 'CLOSED' || this.ticket?.status === 'RESOLVED'; }
}
