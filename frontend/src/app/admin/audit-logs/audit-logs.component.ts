import { Component, OnInit } from '@angular/core';
import { FormControl } from '@angular/forms';
import { debounceTime } from 'rxjs/operators';
import { AnalyticsService } from '../../core/services/analytics.service';
import { AuditLog } from '../../shared/models/notification.model';

@Component({
  selector: 'app-admin-audit-logs',
  templateUrl: './audit-logs.component.html'
})
export class AdminAuditLogsComponent implements OnInit {
  pageTitle = 'Audit Logs';
  logs: AuditLog[] = [];
  loading = false;
  totalPages = 0;
  totalElements = 0;
  page = 0;
  size = 20;
  searchCtrl = new FormControl('');
  displayedColumns = ['timestamp', 'user', 'action', 'entity', 'details', 'ip'];

  constructor(private analyticsService: AnalyticsService) {}

  ngOnInit(): void {
    this.loadLogs();
    this.searchCtrl.valueChanges.pipe(debounceTime(400)).subscribe(() => { this.page = 0; this.loadLogs(); });
  }

  loadLogs(): void {
    this.loading = true;
    this.analyticsService.getAuditLogs(this.searchCtrl.value || undefined, undefined, this.page, this.size).subscribe({
      next: (res) => {
        this.logs = res.data.content;
        this.totalElements = res.data.totalElements;
        this.totalPages = res.data.totalPages;
        this.loading = false;
      },
      error: () => { this.loading = false; }
    });
  }

  changePage(p: number): void { this.page = p; this.loadLogs(); }
  get pages(): number[] { return Array.from({ length: this.totalPages }, (_, i) => i); }

  formatDate(d: string): string {
    return new Date(d).toLocaleString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }
}
