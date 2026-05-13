import { Component, Input } from '@angular/core';

@Component({
  selector: 'app-status-badge',
  template: `
    <span class="badge" [ngClass]="getBadgeClass()">
      <span class="badge-dot" [ngClass]="getDotClass()"></span>
      {{ value | titlecase }}
    </span>
  `,
  styles: [`
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      padding: 4px 10px;
      border-radius: 20px;
      font-size: 11px;
      font-weight: 600;
      text-transform: capitalize;
      letter-spacing: 0.3px;
    }
    .badge-dot {
      width: 6px;
      height: 6px;
      border-radius: 50%;
    }
  `]
})
export class StatusBadgeComponent {
  @Input() value = '';
  @Input() type: 'status' | 'priority' | 'category' = 'status';

  getBadgeClass(): string {
    const v = this.value?.toLowerCase().replace('_', '-');
    if (this.type === 'status') {
      const map: Record<string, string> = {
        'open': 'bg-blue-100 text-blue-700',
        'in-progress': 'bg-amber-100 text-amber-700',
        'pending': 'bg-orange-100 text-orange-700',
        'resolved': 'bg-green-100 text-green-700',
        'closed': 'bg-gray-100 text-gray-600'
      };
      return map[v] || '';
    }
    if (this.type === 'priority') {
      const map: Record<string, string> = {
        'low': 'bg-green-100 text-green-700',
        'medium': 'bg-yellow-100 text-yellow-700',
        'high': 'bg-orange-100 text-orange-700',
        'critical': 'bg-red-100 text-red-700'
      };
      return map[v] || '';
    }
    return 'bg-purple-100 text-purple-700';
  }

  getDotClass(): string {
    const v = this.value?.toLowerCase().replace('_', '-');
    const map: Record<string, string> = {
      'open': 'bg-blue-500',
      'in-progress': 'bg-amber-500',
      'pending': 'bg-orange-500',
      'resolved': 'bg-green-500',
      'closed': 'bg-gray-400',
      'low': 'bg-green-500',
      'medium': 'bg-yellow-500',
      'high': 'bg-orange-500',
      'critical': 'bg-red-500'
    };
    return map[v] || 'bg-gray-400';
  }
}
