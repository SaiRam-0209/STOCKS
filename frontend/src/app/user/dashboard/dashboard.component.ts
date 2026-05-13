import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { TicketService } from '../../core/services/ticket.service';
import { UserService } from '../../core/services/user.service';
import { AuthService } from '../../core/services/auth.service';
import { Ticket } from '../../shared/models/ticket.model';
import { User } from '../../shared/models/user.model';

@Component({
  selector: 'app-user-dashboard',
  templateUrl: './dashboard.component.html',
  styleUrls: ['./dashboard.component.scss']
})
export class UserDashboardComponent implements OnInit {
  pageTitle = 'Dashboard';
  user: User | null = null;
  recentTickets: Ticket[] = [];
  loading = true;
  stats = { total: 0, open: 0, inProgress: 0, resolved: 0, closed: 0 };
  greeting = '';

  constructor(
    private ticketService: TicketService,
    private userService: UserService,
    private authService: AuthService,
    private router: Router
  ) {}

  ngOnInit(): void {
    this.setGreeting();
    this.loadData();
  }

  setGreeting(): void {
    const hour = new Date().getHours();
    if (hour < 12) this.greeting = 'Good morning';
    else if (hour < 18) this.greeting = 'Good afternoon';
    else this.greeting = 'Good evening';
  }

  loadData(): void {
    this.userService.getProfile().subscribe(res => {
      if (res.success) {
        this.user = res.data;
        this.stats.total = res.data.totalTickets;
        this.stats.open = res.data.openTickets;
        this.stats.resolved = res.data.resolvedTickets;
      }
    });

    this.ticketService.getMyTickets({
      page: 0, size: 5, sortBy: 'createdAt', sortDir: 'desc'
    }).subscribe(res => {
      if (res.success) {
        this.recentTickets = res.data.content;
        this.loading = false;
        this.recentTickets.forEach(t => {
          if (t.status === 'IN_PROGRESS') this.stats.inProgress++;
          if (t.status === 'CLOSED') this.stats.closed++;
        });
      }
    });
  }

  createTicket(): void { this.router.navigate(['/user/tickets/create']); }
  viewTickets(): void { this.router.navigate(['/user/tickets']); }
  viewTicket(id: number): void { this.router.navigate(['/user/tickets', id]); }

  getStatusClass(status: string): string {
    const m: Record<string, string> = {
      'OPEN': 'badge--open', 'IN_PROGRESS': 'badge--in-progress',
      'PENDING': 'badge--pending', 'RESOLVED': 'badge--resolved', 'CLOSED': 'badge--closed'
    };
    return 'badge ' + (m[status] || '');
  }

  getPriorityClass(p: string): string {
    const m: Record<string, string> = {
      'LOW': 'badge--low', 'MEDIUM': 'badge--medium',
      'HIGH': 'badge--high', 'CRITICAL': 'badge--critical'
    };
    return 'badge ' + (m[p] || '');
  }

  formatDate(date: string): string {
    return new Date(date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  }
}
