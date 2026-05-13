import { Component } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { MatSnackBar } from '@angular/material/snack-bar';
import { AuthService } from '../../core/services/auth.service';

@Component({
  selector: 'app-login',
  templateUrl: './login.component.html',
  styleUrls: ['./login.component.scss']
})
export class LoginComponent {
  form: FormGroup;
  loading = false;
  hidePassword = true;

  constructor(
    private fb: FormBuilder,
    private authService: AuthService,
    private router: Router,
    private snackBar: MatSnackBar
  ) {
    this.form = this.fb.group({
      email: ['', [Validators.required, Validators.email]],
      password: ['', [Validators.required, Validators.minLength(1)]]
    });

    if (this.authService.isLoggedIn()) {
      const user = this.authService.getCurrentUser();
      this.router.navigate([user?.role === 'ADMIN' ? '/admin/dashboard' : '/user/dashboard']);
    }
  }

  getEmailError(): string {
    const c = this.form.get('email');
    if (c?.hasError('required')) return 'Email address is required';
    if (c?.hasError('email')) return 'Please enter a valid email address (e.g., user@example.com)';
    return '';
  }

  getPasswordError(): string {
    const c = this.form.get('password');
    if (c?.hasError('required')) return 'Password is required';
    return '';
  }

  onSubmit(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }

    this.loading = true;
    this.authService.login(this.form.value).subscribe({
      next: (res) => {
        this.loading = false;
        this.snackBar.open(`Welcome back, ${res.data.name}!`, '✕',
          { duration: 3000, panelClass: ['snack-success'] });
        this.router.navigate([res.data.role === 'ADMIN' ? '/admin/dashboard' : '/user/dashboard']);
      },
      error: (err) => {
        this.loading = false;
        const msg = err.error?.message || 'Invalid credentials. Please try again.';
        this.snackBar.open(msg, '✕', { duration: 5000, panelClass: ['snack-error'] });
      }
    });
  }
}
