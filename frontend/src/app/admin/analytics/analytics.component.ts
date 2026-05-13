import { Component, OnInit } from '@angular/core';
import { ChartConfiguration, ChartData, ChartType } from 'chart.js';
import { AnalyticsService } from '../../core/services/analytics.service';
import { TicketService } from '../../core/services/ticket.service';
import { MatSnackBar } from '@angular/material/snack-bar';
import { Analytics } from '../../shared/models/notification.model';

@Component({
  selector: 'app-admin-analytics',
  templateUrl: './analytics.component.html',
  styleUrls: ['./analytics.component.scss']
})
export class AdminAnalyticsComponent implements OnInit {
  pageTitle = 'Analytics & Reports';
  analytics: Analytics | null = null;
  loading = true;
  exportingCSV = false;
  exportingPDF = false;

  // Doughnut - Status
  statusChartData: ChartData<'doughnut'> = {
    labels: [],
    datasets: [{ data: [], backgroundColor: ['#1976d2','#f57f17','#e65100','#2e7d32','#616161'] }]
  };
  doughnutOptions: ChartConfiguration['options'] = {
    responsive: true,
    plugins: { legend: { position: 'right' } }
  };

  // Bar - Priority
  priorityChartData: ChartData<'bar'> = {
    labels: [],
    datasets: [{
      data: [],
      backgroundColor: ['#4caf50','#ff9800','#ff5722','#f44336'],
      borderRadius: 6
    }]
  };
  barOptions: ChartConfiguration['options'] = {
    responsive: true,
    plugins: { legend: { display: false } },
    scales: { y: { beginAtZero: true } }
  };

  // Line - Trend
  trendChartData: ChartData<'line'> = {
    labels: [],
    datasets: [{
      data: [],
      borderColor: '#3949ab',
      backgroundColor: 'rgba(57,73,171,0.1)',
      tension: 0.4,
      fill: true,
      pointRadius: 4,
      pointBackgroundColor: '#3949ab'
    }]
  };
  lineOptions: ChartConfiguration['options'] = {
    responsive: true,
    plugins: { legend: { display: false } },
    scales: { y: { beginAtZero: true } }
  };

  // Polar - Category
  categoryChartData: ChartData<'polarArea'> = {
    labels: [],
    datasets: [{ data: [] }]
  };

  constructor(
    private analyticsService: AnalyticsService,
    private ticketService: TicketService,
    private snackBar: MatSnackBar
  ) {}

  ngOnInit(): void {
    this.loadAnalytics();
  }

  loadAnalytics(): void {
    this.analyticsService.getAnalytics().subscribe(res => {
      this.loading = false;
      if (res.success) {
        this.analytics = res.data;
        this.buildCharts();
      }
    });
  }

  buildCharts(): void {
    if (!this.analytics) return;

    // Status chart
    const statusEntries = Object.entries(this.analytics.ticketsByStatus);
    this.statusChartData = {
      labels: statusEntries.map(([k]) => k.replace('_', ' ')),
      datasets: [{ data: statusEntries.map(([, v]) => v), backgroundColor: ['#1976d2','#f57f17','#e65100','#2e7d32','#616161'], hoverOffset: 4 }]
    };

    // Priority chart
    const priorityEntries = Object.entries(this.analytics.ticketsByPriority);
    this.priorityChartData = {
      labels: priorityEntries.map(([k]) => k),
      datasets: [{ data: priorityEntries.map(([, v]) => v), backgroundColor: ['#4caf50','#ff9800','#ff5722','#f44336'], borderRadius: 8 }]
    };

    // Trend chart
    this.trendChartData = {
      labels: this.analytics.ticketsTrend.map(t => t.date),
      datasets: [{
        data: this.analytics.ticketsTrend.map(t => t.count),
        label: 'New Tickets',
        borderColor: '#3949ab',
        backgroundColor: 'rgba(57,73,171,0.1)',
        tension: 0.4,
        fill: true,
        pointRadius: 4,
        pointBackgroundColor: '#3949ab'
      }]
    };

    // Category chart
    const catEntries = Object.entries(this.analytics.ticketsByCategory);
    this.categoryChartData = {
      labels: catEntries.map(([k]) => k.replace('_', ' ')),
      datasets: [{ data: catEntries.map(([, v]) => v) }]
    };
  }

  exportCSV(): void {
    this.exportingCSV = true;
    this.ticketService.exportCSV().subscribe({
      next: (blob) => {
        this.exportingCSV = false;
        this.downloadBlob(blob, 'tickets-report.csv');
        this.snackBar.open('CSV exported successfully!', '✕', { duration: 3000, panelClass: ['snack-success'] });
      },
      error: () => {
        this.exportingCSV = false;
        this.snackBar.open('Failed to export CSV.', '✕', { duration: 3000, panelClass: ['snack-error'] });
      }
    });
  }

  exportPDF(): void {
    this.exportingPDF = true;
    this.ticketService.exportPDF().subscribe({
      next: (blob) => {
        this.exportingPDF = false;
        this.downloadBlob(blob, 'tickets-report.pdf');
        this.snackBar.open('PDF exported successfully!', '✕', { duration: 3000, panelClass: ['snack-success'] });
      },
      error: () => {
        this.exportingPDF = false;
        this.snackBar.open('Failed to export PDF.', '✕', { duration: 3000, panelClass: ['snack-error'] });
      }
    });
  }

  private downloadBlob(blob: Blob, fileName: string): void {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = fileName;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }
}
