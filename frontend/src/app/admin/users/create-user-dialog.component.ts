import { Component } from '@angular/core';
import { FormBuilder, FormGroup, Validators, AbstractControl, ValidationErrors } from '@angular/forms';
import { MatDialogRef } from '@angular/material/dialog';
import { MatSnackBar } from '@angular/material/snack-bar';
import { UserService } from '../../core/services/user.service';

function passwordMatch(c: AbstractControl): ValidationErrors | null {
  const p = c.get('password');
  const cp = c.get('confirmPassword');
  if (p && cp && p.value !== cp.value) { cp.setErrors({ passwordMismatch: true }); return { passwordMismatch: true }; }
  return null;
}

@Component({
  selector: 'app-create-user-dialog',
  template: `
    <h2 mat-dialog-title style="font-weight:700; color:#1a237e;">Create New User</h2>
    <mat-dialog-content style="min-width:480px; padding:8px 0 0;">
      <form [formGroup]="form">
        <div class="form-row" style="margin-bottom:12px;">
          <mat-form-field appearance="outline">
            <mat-label>Full Name *</mat-label>
            <input matInput formControlName="name">
            <mat-error *ngIf="form.get('name')?.hasError('required')">Name is required</mat-error>
            <mat-error *ngIf="form.get('name')?.hasError('pattern')">Invalid name format</mat-error>
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Email *</mat-label>
            <input matInput type="email" formControlName="email">
            <mat-error *ngIf="form.get('email')?.hasError('required')">Email is required</mat-error>
            <mat-error *ngIf="form.get('email')?.hasError('email')">Invalid email address</mat-error>
          </mat-form-field>
        </div>
        <div class="form-row" style="margin-bottom:12px;">
          <mat-form-field appearance="outline">
            <mat-label>Password *</mat-label>
            <input matInput [type]="hidePass ? 'password' : 'text'" formControlName="password">
            <button mat-icon-button matSuffix type="button" (click)="hidePass = !hidePass"><mat-icon>{{ hidePass ? 'visibility_off' : 'visibility' }}</mat-icon></button>
            <mat-error *ngIf="form.get('password')?.hasError('pattern')">Must contain uppercase, lowercase, number, special char</mat-error>
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Confirm Password *</mat-label>
            <input matInput [type]="hidePass ? 'password' : 'text'" formControlName="confirmPassword">
            <mat-error *ngIf="form.get('confirmPassword')?.hasError('passwordMismatch')">Passwords do not match</mat-error>
          </mat-form-field>
        </div>
        <div class="form-row" style="margin-bottom:12px;">
          <mat-form-field appearance="outline">
            <mat-label>Phone</mat-label>
            <input matInput formControlName="phone">
            <mat-error *ngIf="form.get('phone')?.hasError('pattern')">Invalid phone number (10-15 digits)</mat-error>
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Department</mat-label>
            <input matInput formControlName="department">
          </mat-form-field>
        </div>
      </form>
    </mat-dialog-content>
    <mat-dialog-actions align="end" style="padding:16px 0 0; gap:10px;">
      <button mat-stroked-button mat-dialog-close>Cancel</button>
      <button mat-raised-button color="primary" (click)="create()" [disabled]="loading" style="border-radius:8px; min-width:120px;">
        <mat-spinner *ngIf="loading" diameter="18" style="display:inline-block; margin-right:6px;"></mat-spinner>
        {{ loading ? 'Creating...' : 'Create User' }}
      </button>
    </mat-dialog-actions>
  `
})
export class CreateUserDialogComponent {
  form: FormGroup;
  loading = false;
  hidePass = true;

  constructor(
    private fb: FormBuilder,
    private userService: UserService,
    private dialogRef: MatDialogRef<CreateUserDialogComponent>,
    private snackBar: MatSnackBar
  ) {
    this.form = this.fb.group({
      name: ['', [Validators.required, Validators.minLength(2), Validators.pattern(/^[a-zA-Z\s''-]+$/)]],
      email: ['', [Validators.required, Validators.email]],
      password: ['', [Validators.required, Validators.minLength(8), Validators.pattern(/^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$/)]],
      confirmPassword: ['', Validators.required],
      phone: ['', [Validators.pattern(/^[+]?[0-9]{10,15}$/)]],
      department: ['']
    }, { validators: passwordMatch });
  }

  create(): void {
    if (this.form.invalid) { this.form.markAllAsTouched(); return; }
    this.loading = true;
    this.userService.createUser(this.form.value).subscribe({
      next: () => {
        this.loading = false;
        this.snackBar.open('User created successfully!', '✕', { duration: 3000, panelClass: ['snack-success'] });
        this.dialogRef.close(true);
      },
      error: (err) => {
        this.loading = false;
        this.snackBar.open(err.error?.message || 'Failed to create user.', '✕', { duration: 4000, panelClass: ['snack-error'] });
      }
    });
  }
}
