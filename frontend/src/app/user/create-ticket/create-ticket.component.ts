import { Component } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { MatSnackBar } from '@angular/material/snack-bar';
import { TicketService } from '../../core/services/ticket.service';

@Component({
  selector: 'app-create-ticket',
  templateUrl: './create-ticket.component.html',
  styleUrls: ['./create-ticket.component.scss']
})
export class CreateTicketComponent {
  pageTitle = 'New Ticket';
  form: FormGroup;
  loading = false;
  selectedFiles: File[] = [];

  categories = [
    { value: 'TECHNICAL', label: 'Technical Issue', icon: '⚙️' },
    { value: 'BILLING', label: 'Billing & Payments', icon: '💳' },
    { value: 'GENERAL', label: 'General Inquiry', icon: '❓' },
    { value: 'FEATURE_REQUEST', label: 'Feature Request', icon: '✨' },
    { value: 'BUG_REPORT', label: 'Bug Report', icon: '🐛' },
    { value: 'ACCOUNT', label: 'Account Issue', icon: '👤' },
    { value: 'OTHER', label: 'Other', icon: '📋' }
  ];

  priorities = [
    { value: 'LOW', label: 'Low', desc: 'Non-urgent issue', color: '#2e7d32' },
    { value: 'MEDIUM', label: 'Medium', desc: 'Moderate impact', color: '#f57f17' },
    { value: 'HIGH', label: 'High', desc: 'Significant impact', color: '#e65100' },
    { value: 'CRITICAL', label: 'Critical', desc: 'Service down/urgent', color: '#c62828' }
  ];

  constructor(
    private fb: FormBuilder,
    private ticketService: TicketService,
    private router: Router,
    private snackBar: MatSnackBar
  ) {
    this.form = this.fb.group({
      subject: ['', [
        Validators.required,
        Validators.minLength(5),
        Validators.maxLength(200),
        Validators.pattern(/^[a-zA-Z0-9\s.,!?'"()\-]+$/)
      ]],
      category: ['', [Validators.required]],
      priority: ['', [Validators.required]],
      description: ['', [
        Validators.required,
        Validators.minLength(20),
        Validators.maxLength(5000)
      ]]
    });
  }

  getError(field: string): string {
    const c = this.form.get(field);
    if (!c?.errors || !c.touched) return '';
    if (c.hasError('required')) return `${this.getLabel(field)} is required`;
    if (field === 'subject') {
      if (c.hasError('minlength')) return 'Subject must be at least 5 characters';
      if (c.hasError('maxlength')) return 'Subject must not exceed 200 characters';
      if (c.hasError('pattern')) return 'Subject contains invalid characters. Use letters, numbers, and common punctuation';
    }
    if (field === 'description') {
      if (c.hasError('minlength')) return 'Please provide more detail (at least 20 characters)';
      if (c.hasError('maxlength')) return 'Description must not exceed 5000 characters';
    }
    return '';
  }

  getLabel(field: string): string {
    const labels: Record<string, string> = { subject: 'Subject', category: 'Category', priority: 'Priority', description: 'Description' };
    return labels[field] || field;
  }

  get descLength(): number { return this.form.get('description')?.value?.length || 0; }

  onFilesSelected(files: File[]): void { this.selectedFiles = files; }

  onSubmit(): void {
    if (this.form.invalid) { this.form.markAllAsTouched(); return; }
    this.loading = true;
    this.ticketService.createTicket(this.form.value, this.selectedFiles).subscribe({
      next: (res) => {
        this.loading = false;
        this.snackBar.open(`Ticket ${res.data.ticketNumber} created successfully!`, '✕',
          { duration: 4000, panelClass: ['snack-success'] });
        this.router.navigate(['/user/tickets', res.data.id]);
      },
      error: (err) => {
        this.loading = false;
        const msg = err.error?.message || 'Failed to create ticket. Please try again.';
        this.snackBar.open(msg, '✕', { duration: 5000, panelClass: ['snack-error'] });
      }
    });
  }

  cancel(): void { this.router.navigate(['/user/tickets']); }
}
