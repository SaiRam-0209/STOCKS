import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { AnalyticsService } from '../../core/services/analytics.service';
import { TicketService } from '../../core/services/ticket.service';
import { Analytics } from '../../shared/models/notification.model';
import { Ticket } from '../../shared/models/ticket.model';

@Component({
  selector: 'app-admin-dashboard',
  templateUrl: './dashboard.component.html',
  styleUrls: ['./dashboard.component.scss']
})
export class AdminDashboardComponent implements OnInit {
  pageTitle = 'Admin Dashboard';
  analytics: Analytics | null = null;
  recentTickets: Ticket[] = [];
  loading = true;

  statCards = [
    { key: 'totalTickets', label: 'Total Tickets', icon: 'confirmation_number', color: '#3949ab', bg: '#e8eaf6' },
    { key: 'openTickets', label: 'Open', icon: 'radio_button_unchecked', color: '#0277bd', bg: '#e1f5fe' },
    { key: 'inProgressTickets', label: 'In Progress', icon: 'autorenew', color: '#f57f17', bg: '#fff8e1' },
    { key: 'resolvedTickets', label: 'Resolved', icon: 'check_circle', color: '#2e7d32', bg: '#e8f5e9' },
    { key: 'totalUsers', label: 'Users', icon: 'people', color: '#6a1b9a', bg: '#f3e5f5' },
    { key: 'pendingAIResponses', label: 'AI Pending', icon: 'smart_toy', color: '#00695c', bg: '#e0f2f1' }
  ];

  constructor(
    private analyticsService: AnalyticsService,
    private ticketService: TicketService,
    private router: Router
  ) {}

  ngOnInit(): void {
    this.loadData();
  }

  loadData(): void {
    this.analyticsService.getAnalytics().subscribe(res => {
      if (res.success) { this.analytics = res.data; }
    });

    this.ticketService.getAllTickets({ page: 0, size: 8, sortBy: 'createdAt', sortDir: 'desc' }).subscribe(res => {
      if (res.success) {
        this.recentTickets = res.data.content;
        this.loading = false;
      }
    });
  }

  getStatValue(key: string): number {
    return (this.analytics as any)?.[key] || 0;
  }

  viewTicket(id: number): void { this.router.navigate(['/admin/tickets', id]); }
  viewAllTickets(): void { this.router.navigate(['/admin/tickets']); }
  viewAIResponses(): void { this.router.navigate(['/admin/ai-responses']); }

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
    return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  }
}
