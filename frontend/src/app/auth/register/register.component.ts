import { Component } from '@angular/core';
import { FormBuilder, FormGroup, Validators, AbstractControl, ValidationErrors } from '@angular/forms';
import { Router } from '@angular/router';
import { MatSnackBar } from '@angular/material/snack-bar';
import { AuthService } from '../../core/services/auth.service';

function passwordMatchValidator(control: AbstractControl): ValidationErrors | null {
  const pass = control.get('password');
  const confirm = control.get('confirmPassword');
  if (pass && confirm && pass.value !== confirm.value) {
    confirm.setErrors({ passwordMismatch: true });
    return { passwordMismatch: true };
  }
  return null;
}

@Component({
  selector: 'app-register',
  templateUrl: './register.component.html',
  styleUrls: ['./register.component.scss']
})
export class RegisterComponent {
  form: FormGroup;
  loading = false;
  hidePassword = true;
  hideConfirm = true;

  constructor(
    private fb: FormBuilder,
    private authService: AuthService,
    private router: Router,
    private snackBar: MatSnackBar
  ) {
    this.form = this.fb.group({
      name: ['', [
        Validators.required,
        Validators.minLength(2),
        Validators.maxLength(100),
        Validators.pattern(/^[a-zA-Z\s''-]+$/)
      ]],
      email: ['', [Validators.required, Validators.email, Validators.maxLength(150)]],
      password: ['', [
        Validators.required,
        Validators.minLength(8),
        Validators.maxLength(20),
        Validators.pattern(/^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$/)
      ]],
      confirmPassword: ['', [Validators.required]],
      phone: ['', [Validators.pattern(/^[+]?[0-9]{10,15}$/)]],
      department: ['', [
        Validators.maxLength(100),
        Validators.pattern(/^[a-zA-Z\s&-]*$/)
      ]]
    }, { validators: passwordMatchValidator });
  }

  getError(field: string): string {
    const c = this.form.get(field);
    if (!c?.errors || !c.touched) return '';
    if (c.hasError('required')) return `${this.getLabel(field)} is required`;
    if (field === 'name') {
      if (c.hasError('minlength')) return 'Name must be at least 2 characters';
      if (c.hasError('maxlength')) return 'Name must not exceed 100 characters';
      if (c.hasError('pattern')) return 'Name can only contain letters, spaces, hyphens, and apostrophes';
    }
    if (field === 'email') {
      if (c.hasError('email')) return 'Please enter a valid email address';
    }
    if (field === 'password') {
      if (c.hasError('minlength')) return 'Password must be at least 8 characters';
      if (c.hasError('maxlength')) return 'Password must not exceed 20 characters';
      if (c.hasError('pattern')) return 'Password must contain uppercase, lowercase, number, and special character (@$!%*?&)';
    }
    if (field === 'confirmPassword') {
      if (c.hasError('passwordMismatch')) return 'Passwords do not match';
    }
    if (field === 'phone' && c.hasError('pattern')) return 'Please enter a valid phone number (10-15 digits)';
    if (field === 'department' && c.hasError('pattern')) return 'Department can only contain letters, spaces, and &-';
    return '';
  }

  getLabel(field: string): string {
    const labels: Record<string, string> = {
      name: 'Full name', email: 'Email', password: 'Password',
      confirmPassword: 'Confirm password', phone: 'Phone', department: 'Department'
    };
    return labels[field] || field;
  }

  getPasswordStrength(): { level: number; label: string; color: string } {
    const pass = this.form.get('password')?.value || '';
    let score = 0;
    if (pass.length >= 8) score++;
    if (/[A-Z]/.test(pass)) score++;
    if (/[a-z]/.test(pass)) score++;
    if (/\d/.test(pass)) score++;
    if (/[@$!%*?&]/.test(pass)) score++;
    if (score <= 2) return { level: score, label: 'Weak', color: '#f44336' };
    if (score <= 3) return { level: score, label: 'Fair', color: '#ff9800' };
    if (score <= 4) return { level: score, label: 'Good', color: '#2196f3' };
    return { level: score, label: 'Strong', color: '#4caf50' };
  }

  onSubmit(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }

    this.loading = true;
    this.authService.register(this.form.value).subscribe({
      next: (res) => {
        this.loading = false;
        this.snackBar.open('Account created! Welcome to AI Support Portal.', '✕',
          { duration: 4000, panelClass: ['snack-success'] });
        this.router.navigate(['/user/dashboard']);
      },
      error: (err) => {
        this.loading = false;
        const msg = err.error?.message || 'Registration failed. Please try again.';
        this.snackBar.open(msg, '✕', { duration: 5000, panelClass: ['snack-error'] });
      }
    });
  }
}
