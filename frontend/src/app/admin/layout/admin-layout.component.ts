import { Component } from '@angular/core';

@Component({
  selector: 'app-admin-layout',
  template: `
    <div class="layout-wrapper">
      <app-sidebar></app-sidebar>
      <div class="main-content">
        <app-header [title]="pageTitle" (menuToggle)="toggleSidebar()"></app-header>
        <div class="content-area">
          <router-outlet (activate)="onRouteActivate($event)"></router-outlet>
        </div>
      </div>
    </div>
  `
})
export class AdminLayoutComponent {
  pageTitle = 'Admin Dashboard';

  onRouteActivate(component: any): void {
    this.pageTitle = component.pageTitle || 'Admin Dashboard';
  }

  toggleSidebar(): void {}
}
