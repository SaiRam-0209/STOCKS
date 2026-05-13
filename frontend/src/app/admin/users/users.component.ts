import { Component, OnInit } from '@angular/core';
import { FormControl } from '@angular/forms';
import { MatDialog } from '@angular/material/dialog';
import { MatSnackBar } from '@angular/material/snack-bar';
import { debounceTime } from 'rxjs/operators';
import { UserService } from '../../core/services/user.service';
import { User } from '../../shared/models/user.model';
import { CreateUserDialogComponent } from './create-user-dialog.component';

@Component({
  selector: 'app-admin-users',
  templateUrl: './users.component.html',
  styleUrls: ['./users.component.scss']
})
export class AdminUsersComponent implements OnInit {
  pageTitle = 'User Management';
  users: User[] = [];
  loading = false;
  totalElements = 0;
  totalPages = 0;
  searchCtrl = new FormControl('');
  roleFilter: string | undefined;
  statusFilter: boolean | undefined;
  page = 0;
  size = 10;

  displayedColumns = ['name','email','role','department','status','tickets','created','actions'];

  constructor(private userService: UserService, private dialog: MatDialog, private snackBar: MatSnackBar) {}

  ngOnInit(): void {
    this.loadUsers();
    this.searchCtrl.valueChanges.pipe(debounceTime(400)).subscribe(() => { this.page = 0; this.loadUsers(); });
  }

  loadUsers(): void {
    this.loading = true;
    this.userService.getAllUsers(
      this.searchCtrl.value || undefined,
      this.roleFilter, this.statusFilter, this.page, this.size
    ).subscribe({
      next: (res) => {
        this.users = res.data.content;
        this.totalElements = res.data.totalElements;
        this.totalPages = res.data.totalPages;
        this.loading = false;
      },
      error: () => { this.loading = false; }
    });
  }

  toggleStatus(user: User): void {
    this.userService.toggleUserStatus(user.id).subscribe({
      next: (res) => {
        const idx = this.users.findIndex(u => u.id === user.id);
        if (idx >= 0) this.users[idx] = res.data;
        this.users = [...this.users];
        this.snackBar.open(`User ${res.data.isActive ? 'activated' : 'deactivated'}.`, '✕', { duration: 3000, panelClass: ['snack-success'] });
      }
    });
  }

  deleteUser(user: User): void {
    if (!confirm(`Are you sure you want to delete ${user.name}? This action cannot be undone.`)) return;
    this.userService.deleteUser(user.id).subscribe({
      next: () => {
        this.users = this.users.filter(u => u.id !== user.id);
        this.snackBar.open('User deleted.', '✕', { duration: 3000, panelClass: ['snack-success'] });
      },
      error: (err) => this.snackBar.open(err.error?.message || 'Failed to delete user.', '✕', { duration: 4000, panelClass: ['snack-error'] })
    });
  }

  openCreateDialog(): void {
    const ref = this.dialog.open(CreateUserDialogComponent, { width: '520px', disableClose: true });
    ref.afterClosed().subscribe(result => { if (result) this.loadUsers(); });
  }

  changePage(p: number): void { this.page = p; this.loadUsers(); }

  get pages(): number[] { return Array.from({ length: this.totalPages }, (_, i) => i); }

  formatDate(d: string): string {
    return new Date(d).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
  }
}
