import { Component } from '@angular/core';
import { Router } from '@angular/router';

@Component({
  selector: 'app-user-layout',
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
export class UserLayoutComponent {
  pageTitle = 'Dashboard';

  onRouteActivate(component: any): void {
    this.pageTitle = component.pageTitle || 'Dashboard';
  }

  toggleSidebar(): void {}
}
