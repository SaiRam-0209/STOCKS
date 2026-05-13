import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { MatTableModule } from '@angular/material/table';
import { MatPaginatorModule } from '@angular/material/paginator';
import { MatSortModule } from '@angular/material/sort';
import { MatSelectModule } from '@angular/material/select';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatCardModule } from '@angular/material/card';
import { MatChipsModule } from '@angular/material/chips';
import { MatDialogModule } from '@angular/material/dialog';
import { MatSnackBarModule } from '@angular/material/snack-bar';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatMenuModule } from '@angular/material/menu';
import { MatTabsModule } from '@angular/material/tabs';
import { MatDividerModule } from '@angular/material/divider';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { NgChartsModule } from 'ng2-charts';
import { SharedModule } from '../shared/shared.module';
import { AdminLayoutComponent } from './layout/admin-layout.component';
import { AdminDashboardComponent } from './dashboard/dashboard.component';
import { AdminTicketsComponent } from './tickets/tickets.component';
import { AdminTicketDetailComponent } from './ticket-detail/ticket-detail.component';
import { AdminUsersComponent } from './users/users.component';
import { AdminAnalyticsComponent } from './analytics/analytics.component';
import { AdminAuditLogsComponent } from './audit-logs/audit-logs.component';
import { AdminAIResponsesComponent } from './ai-responses/ai-responses.component';
import { CreateUserDialogComponent } from './users/create-user-dialog.component';

const routes: Routes = [
  {
    path: '',
    component: AdminLayoutComponent,
    children: [
      { path: 'dashboard', component: AdminDashboardComponent },
      { path: 'tickets', component: AdminTicketsComponent },
      { path: 'tickets/:id', component: AdminTicketDetailComponent },
      { path: 'users', component: AdminUsersComponent },
      { path: 'analytics', component: AdminAnalyticsComponent },
      { path: 'audit-logs', component: AdminAuditLogsComponent },
      { path: 'ai-responses', component: AdminAIResponsesComponent },
      { path: '', redirectTo: 'dashboard', pathMatch: 'full' }
    ]
  }
];

@NgModule({
  declarations: [
    AdminLayoutComponent,
    AdminDashboardComponent,
    AdminTicketsComponent,
    AdminTicketDetailComponent,
    AdminUsersComponent,
    AdminAnalyticsComponent,
    AdminAuditLogsComponent,
    AdminAIResponsesComponent,
    CreateUserDialogComponent
  ],
  imports: [
    SharedModule,
    RouterModule.forChild(routes),
    NgChartsModule,
    MatTableModule, MatPaginatorModule, MatSortModule, MatSelectModule,
    MatInputModule, MatButtonModule, MatIconModule, MatCardModule,
    MatChipsModule, MatDialogModule, MatSnackBarModule, MatProgressSpinnerModule,
    MatProgressBarModule, MatTooltipModule, MatMenuModule, MatTabsModule,
    MatDividerModule, MatSlideToggleModule
  ]
})
export class AdminModule {}
