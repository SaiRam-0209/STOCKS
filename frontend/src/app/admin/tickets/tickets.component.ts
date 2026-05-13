import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { FormControl } from '@angular/forms';
import { debounceTime } from 'rxjs/operators';
import { TicketService } from '../../core/services/ticket.service';
import { Ticket, TicketFilters, TicketStatus, TicketPriority, TicketCategory } from '../../shared/models/ticket.model';

@Component({
  selector: 'app-admin-tickets',
  templateUrl: './tickets.component.html',
  styleUrls: ['./tickets.component.scss']
})
export class AdminTicketsComponent implements OnInit {
  pageTitle = 'All Tickets';
  tickets: Ticket[] = [];
  loading = false;
  totalElements = 0;
  totalPages = 0;
  searchCtrl = new FormControl('');

  filters: TicketFilters = { page: 0, size: 10, sortBy: 'createdAt', sortDir: 'desc' };

  statuses = ['OPEN','IN_PROGRESS','PENDING','RESOLVED','CLOSED'];
  priorities = ['LOW','MEDIUM','HIGH','CRITICAL'];
  categories = ['TECHNICAL','BILLING','GENERAL','FEATURE_REQUEST','BUG_REPORT','ACCOUNT','OTHER'];

  displayedColumns = ['ticketNumber','subject','user','priority','status','assignedTo','messages','createdAt','actions'];

  constructor(private ticketService: TicketService, private router: Router) {}

  ngOnInit(): void {
    this.loadTickets();
    this.searchCtrl.valueChanges.pipe(debounceTime(400)).subscribe(v => {
      this.filters.search = v || undefined;
      this.filters.page = 0;
      this.loadTickets();
    });
  }

  loadTickets(): void {
    this.loading = true;
    this.ticketService.getAllTickets(this.filters).subscribe({
      next: (res) => {
        this.tickets = res.data.content;
        this.totalElements = res.data.totalElements;
        this.totalPages = res.data.totalPages;
        this.loading = false;
      },
      error: () => { this.loading = false; }
    });
  }

  applyFilter(key: keyof TicketFilters, value: any): void {
    (this.filters as any)[key] = value || undefined;
    this.filters.page = 0;
    this.loadTickets();
  }

  clearFilters(): void {
    this.searchCtrl.setValue('');
    this.filters = { page: 0, size: 10, sortBy: 'createdAt', sortDir: 'desc' };
    this.loadTickets();
  }

  changePage(page: number): void { this.filters.page = page; this.loadTickets(); }

  get pages(): number[] { return Array.from({ length: this.totalPages }, (_, i) => i); }

  viewTicket(id: number): void { this.router.navigate(['/admin/tickets', id]); }

  getStatusClass(s: string): string {
    const m: Record<string, string> = { OPEN: 'badge--open', IN_PROGRESS: 'badge--in-progress', PENDING: 'badge--pending', RESOLVED: 'badge--resolved', CLOSED: 'badge--closed' };
    return 'badge ' + (m[s] || '');
  }

  getPriorityClass(p: string): string {
    const m: Record<string, string> = { LOW: 'badge--low', MEDIUM: 'badge--medium', HIGH: 'badge--high', CRITICAL: 'badge--critical' };
    return 'badge ' + (m[p] || '');
  }

  formatDate(d: string): string {
    return new Date(d).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
  }
}
