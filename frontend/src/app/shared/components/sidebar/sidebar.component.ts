import { Component, OnInit, Input } from '@angular/core';
import { Router } from '@angular/router';
import { AuthService } from '../../../core/services/auth.service';

export interface NavItem {
  label: string;
  icon: string;
  route: string;
  badge?: number;
}

@Component({
  selector: 'app-sidebar',
  templateUrl: './sidebar.component.html',
  styleUrls: ['./sidebar.component.scss']
})
export class SidebarComponent implements OnInit {
  @Input() isOpen = true;
  @Input() pendingAiCount = 0;

  isAdmin = false;
  userName = '';
  userEmail = '';
  userInitials = '';

  adminNavItems: NavItem[] = [
    { label: 'Dashboard', icon: 'dashboard', route: '/admin/dashboard' },
    { label: 'All Tickets', icon: 'confirmation_number', route: '/admin/tickets' },
    { label: 'AI Responses', icon: 'smart_toy', route: '/admin/ai-responses' },
    { label: 'Users', icon: 'people', route: '/admin/users' },
    { label: 'Analytics', icon: 'analytics', route: '/admin/analytics' },
    { label: 'Audit Logs', icon: 'history', route: '/admin/audit-logs' },
  ];

  userNavItems: NavItem[] = [
    { label: 'Dashboard', icon: 'dashboard', route: '/user/dashboard' },
    { label: 'My Tickets', icon: 'confirmation_number', route: '/user/tickets' },
    { label: 'New Ticket', icon: 'add_circle', route: '/user/tickets/create' },
    { label: 'Profile', icon: 'person', route: '/user/profile' },
  ];

  constructor(private authService: AuthService, private router: Router) {}

  ngOnInit(): void {
    const user = this.authService.getCurrentUser();
    if (user) {
      this.isAdmin = user.role === 'ADMIN';
      this.userName = user.name;
      this.userEmail = user.email;
      this.userInitials = user.name.split(' ').map(n => n[0]).join('').toUpperCase().substring(0, 2);
    }
  }

  get navItems(): NavItem[] {
    return this.isAdmin ? this.adminNavItems : this.userNavItems;
  }

  logout(): void {
    this.authService.logout();
  }
}
