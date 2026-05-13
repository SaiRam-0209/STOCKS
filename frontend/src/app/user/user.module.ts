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
import { SharedModule } from '../shared/shared.module';
import { UserLayoutComponent } from './layout/user-layout.component';
import { UserDashboardComponent } from './dashboard/dashboard.component';
import { UserTicketsComponent } from './tickets/tickets.component';
import { CreateTicketComponent } from './create-ticket/create-ticket.component';
import { TicketDetailComponent } from './ticket-detail/ticket-detail.component';
import { UserProfileComponent } from './profile/profile.component';

const routes: Routes = [
  {
    path: '',
    component: UserLayoutComponent,
    children: [
      { path: 'dashboard', component: UserDashboardComponent },
      { path: 'tickets', component: UserTicketsComponent },
      { path: 'tickets/create', component: CreateTicketComponent },
      { path: 'tickets/:id', component: TicketDetailComponent },
      { path: 'profile', component: UserProfileComponent },
      { path: '', redirectTo: 'dashboard', pathMatch: 'full' }
    ]
  }
];

@NgModule({
  declarations: [
    UserLayoutComponent,
    UserDashboardComponent,
    UserTicketsComponent,
    CreateTicketComponent,
    TicketDetailComponent,
    UserProfileComponent
  ],
  imports: [
    SharedModule,
    RouterModule.forChild(routes),
    MatTableModule, MatPaginatorModule, MatSortModule, MatSelectModule,
    MatInputModule, MatButtonModule, MatIconModule, MatCardModule,
    MatChipsModule, MatDialogModule, MatSnackBarModule, MatProgressSpinnerModule,
    MatProgressBarModule, MatTooltipModule, MatMenuModule, MatTabsModule, MatDividerModule
  ]
})
export class UserModule {}
