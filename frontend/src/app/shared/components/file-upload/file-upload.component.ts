import { Component, Output, EventEmitter, Input } from '@angular/core';

@Component({
  selector: 'app-file-upload',
  templateUrl: './file-upload.component.html',
  styleUrls: ['./file-upload.component.scss']
})
export class FileUploadComponent {
  @Input() multiple = true;
  @Input() maxFiles = 5;
  @Output() filesSelected = new EventEmitter<File[]>();

  selectedFiles: File[] = [];
  dragOver = false;
  error = '';

  readonly ALLOWED_TYPES = ['application/pdf', 'image/jpeg', 'image/jpg', 'image/png', 'image/gif',
    'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'text/plain', 'application/zip', 'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'];
  readonly MAX_SIZE = 10 * 1024 * 1024;

  onDragOver(e: DragEvent): void {
    e.preventDefault();
    this.dragOver = true;
  }

  onDragLeave(): void { this.dragOver = false; }

  onDrop(e: DragEvent): void {
    e.preventDefault();
    this.dragOver = false;
    if (e.dataTransfer?.files) {
      this.processFiles(Array.from(e.dataTransfer.files));
    }
  }

  onFileInput(e: Event): void {
    const input = e.target as HTMLInputElement;
    if (input.files) {
      this.processFiles(Array.from(input.files));
    }
    input.value = '';
  }

  processFiles(files: File[]): void {
    this.error = '';
    const total = this.selectedFiles.length + files.length;
    if (total > this.maxFiles) {
      this.error = `Maximum ${this.maxFiles} files allowed.`;
      return;
    }

    for (const file of files) {
      if (!this.ALLOWED_TYPES.includes(file.type)) {
        this.error = `File type "${file.type || file.name.split('.').pop()}" is not allowed.`;
        return;
      }
      if (file.size > this.MAX_SIZE) {
        this.error = `File "${file.name}" exceeds 10MB limit.`;
        return;
      }
      if (this.selectedFiles.find(f => f.name === file.name)) {
        this.error = `File "${file.name}" is already added.`;
        return;
      }
    }

    this.selectedFiles = [...this.selectedFiles, ...files];
    this.filesSelected.emit(this.selectedFiles);
  }

  removeFile(index: number): void {
    this.selectedFiles.splice(index, 1);
    this.selectedFiles = [...this.selectedFiles];
    this.filesSelected.emit(this.selectedFiles);
    this.error = '';
  }

  formatSize(bytes: number): string {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / 1048576).toFixed(1) + ' MB';
  }

  getFileIcon(file: File): string {
    const type = file.type;
    if (type.includes('image')) return '🖼️';
    if (type.includes('pdf')) return '📄';
    if (type.includes('word')) return '📝';
    if (type.includes('excel') || type.includes('spreadsheet')) return '📊';
    if (type.includes('zip')) return '🗜️';
    return '📎';
  }
}
