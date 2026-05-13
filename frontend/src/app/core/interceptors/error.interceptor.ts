import { Injectable } from '@angular/core';
import { HttpRequest, HttpHandler, HttpEvent, HttpInterceptor, HttpErrorResponse } from '@angular/common/http';
import { Observable, throwError } from 'rxjs';
import { catchError } from 'rxjs/operators';
import { Router } from '@angular/router';
import { MatSnackBar } from '@angular/material/snack-bar';
import { AuthService } from '../services/auth.service';

@Injectable()
export class ErrorInterceptor implements HttpInterceptor {
  constructor(
    private router: Router,
    private snackBar: MatSnackBar,
    private authService: AuthService
  ) {}

  intercept(request: HttpRequest<any>, next: HttpHandler): Observable<HttpEvent<any>> {
    return next.handle(request).pipe(
      catchError((error: HttpErrorResponse) => {
        if (error.status === 401 && !request.url.includes('/auth/')) {
          this.authService.logout();
          this.snackBar.open('Session expired. Please log in again.', 'Close',
            { duration: 4000, panelClass: ['snack-warn'] });
        } else if (error.status === 403) {
          this.snackBar.open('You do not have permission to perform this action.', 'Close',
            { duration: 4000, panelClass: ['snack-error'] });
        } else if (error.status === 0) {
          this.snackBar.open('Cannot connect to server. Please check your connection.', 'Close',
            { duration: 4000, panelClass: ['snack-error'] });
        }
        return throwError(() => error);
      })
    );
  }
}
