import { Component, OnInit } from '@angular/core';
import { FormBuilder, FormGroup, Validators, AbstractControl, ValidationErrors } from '@angular/forms';
import { MatSnackBar } from '@angular/material/snack-bar';
import { UserService } from '../../core/services/user.service';
import { User } from '../../shared/models/user.model';

function passwordMatch(c: AbstractControl): ValidationErrors | null {
  const p = c.get('newPassword');
  const cp = c.get('confirmPassword');
  if (p && cp && p.value && p.value !== cp.value) {
    cp.setErrors({ passwordMismatch: true });
    return { passwordMismatch: true };
  }
  return null;
}

@Component({
  selector: 'app-user-profile',
  templateUrl: './profile.component.html',
  styleUrls: ['./profile.component.scss']
})
export class UserProfileComponent implements OnInit {
  pageTitle = 'My Profile';
  user: User | null = null;
  profileForm!: FormGroup;
  passwordForm!: FormGroup;
  loading = false;
  savingProfile = false;
  changingPassword = false;
  hideCurrentPass = true;
  hideNewPass = true;
  hideConfirm = true;

  constructor(private fb: FormBuilder, private userService: UserService, private snackBar: MatSnackBar) {}

  ngOnInit(): void {
    this.buildForms();
    this.loadProfile();
  }

  buildForms(): void {
    this.profileForm = this.fb.group({
      name: ['', [
        Validators.required,
        Validators.minLength(2),
        Validators.maxLength(100),
        Validators.pattern(/^[a-zA-Z\s''-]+$/)
      ]],
      phone: ['', [Validators.pattern(/^[+]?[0-9]{10,15}$/)]],
      department: ['', [Validators.maxLength(100), Validators.pattern(/^[a-zA-Z\s&-]*$/)]]
    });

    this.passwordForm = this.fb.group({
      currentPassword: ['', [Validators.required]],
      newPassword: ['', [
        Validators.required,
        Validators.minLength(8),
        Validators.maxLength(20),
        Validators.pattern(/^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$/)
      ]],
      confirmPassword: ['', [Validators.required]]
    }, { validators: passwordMatch });
  }

  loadProfile(): void {
    this.loading = true;
    this.userService.getProfile().subscribe(res => {
      this.loading = false;
      this.user = res.data;
      this.profileForm.patchValue({
        name: res.data.name,
        phone: res.data.phone || '',
        department: res.data.department || ''
      });
    });
  }

  getProfileError(field: string): string {
    const c = this.profileForm.get(field);
    if (!c?.errors || !c.touched) return '';
    if (c.hasError('required')) return `${field} is required`;
    if (field === 'name') {
      if (c.hasError('minlength')) return 'Name must be at least 2 characters';
      if (c.hasError('pattern')) return 'Name can only contain letters, spaces, hyphens';
    }
    if (field === 'phone' && c.hasError('pattern')) return 'Please enter a valid phone number (10-15 digits)';
    if (field === 'department' && c.hasError('pattern')) return 'Invalid department name';
    return '';
  }

  getPasswordError(field: string): string {
    const c = this.passwordForm.get(field);
    if (!c?.errors || !c.touched) return '';
    if (c.hasError('required')) return 'This field is required';
    if (field === 'newPassword' && c.hasError('pattern'))
      return 'Must contain uppercase, lowercase, number, and special character';
    if (field === 'confirmPassword' && c.hasError('passwordMismatch'))
      return 'Passwords do not match';
    return '';
  }

  saveProfile(): void {
    if (this.profileForm.invalid) { this.profileForm.markAllAsTouched(); return; }
    this.savingProfile = true;
    this.userService.updateProfile(this.profileForm.value).subscribe({
      next: (res) => {
        this.savingProfile = false;
        this.user = res.data;
        this.snackBar.open('Profile updated successfully!', '✕', { duration: 3000, panelClass: ['snack-success'] });
      },
      error: (err) => {
        this.savingProfile = false;
        this.snackBar.open(err.error?.message || 'Failed to update profile.', '✕', { duration: 4000, panelClass: ['snack-error'] });
      }
    });
  }

  changePassword(): void {
    if (this.passwordForm.invalid) { this.passwordForm.markAllAsTouched(); return; }
    this.changingPassword = true;
    this.userService.changePassword(this.passwordForm.value).subscribe({
      next: () => {
        this.changingPassword = false;
        this.passwordForm.reset();
        this.snackBar.open('Password changed successfully!', '✕', { duration: 3000, panelClass: ['snack-success'] });
      },
      error: (err) => {
        this.changingPassword = false;
        this.snackBar.open(err.error?.message || 'Failed to change password.', '✕', { duration: 4000, panelClass: ['snack-error'] });
      }
    });
  }

  getUserInitials(): string {
    return this.user?.name?.split(' ').map(n => n[0]).join('').toUpperCase().substring(0, 2) || 'U';
  }

  formatDate(d: string): string {
    return d ? new Date(d).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' }) : 'N/A';
  }
}
