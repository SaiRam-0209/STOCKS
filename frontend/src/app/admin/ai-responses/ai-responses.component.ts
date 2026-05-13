import { Component, OnInit } from '@angular/core';
import { MatSnackBar } from '@angular/material/snack-bar';
import { TicketService } from '../../core/services/ticket.service';
import { AIResponse } from '../../shared/models/ticket.model';
import { Router } from '@angular/router';

@Component({
  selector: 'app-admin-ai-responses',
  templateUrl: './ai-responses.component.html'
})
export class AdminAIResponsesComponent implements OnInit {
  pageTitle = 'AI Response Review';
  responses: AIResponse[] = [];
  loading = false;
  totalPages = 0;
  totalElements = 0;
  page = 0;

  constructor(private ticketService: TicketService, private snackBar: MatSnackBar, private router: Router) {}

  ngOnInit(): void { this.loadResponses(); }

  loadResponses(): void {
    this.loading = true;
    this.ticketService.getPendingAIResponses(this.page).subscribe({
      next: (res) => {
        this.responses = res.data.content;
        this.totalElements = res.data.totalElements;
        this.totalPages = res.data.totalPages;
        this.loading = false;
      },
      error: () => { this.loading = false; }
    });
  }

  review(id: number, status: string): void {
    this.ticketService.reviewAIResponse(id, status).subscribe({
      next: () => {
        this.responses = this.responses.filter(r => r.id !== id);
        this.totalElements--;
        this.snackBar.open(`AI response ${status.toLowerCase()}d!`, '✕', { duration: 3000, panelClass: ['snack-success'] });
      },
      error: (err) => this.snackBar.open(err.error?.message || 'Failed.', '✕', { duration: 4000 })
    });
  }

  viewTicket(ticketId: number): void { this.router.navigate(['/admin/tickets', ticketId]); }

  changePage(p: number): void { this.page = p; this.loadResponses(); }
  get pages(): number[] { return Array.from({ length: this.totalPages }, (_, i) => i); }

  formatDate(d: string): string { return new Date(d).toLocaleString(); }
}
