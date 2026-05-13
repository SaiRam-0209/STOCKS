package com.supportportal.controller;

import com.supportportal.dto.request.ChatMessageRequest;
import com.supportportal.dto.request.TicketCreateRequest;
import com.supportportal.dto.response.*;
import com.supportportal.entity.User;
import com.supportportal.enums.TicketCategory;
import com.supportportal.enums.TicketPriority;
import com.supportportal.enums.TicketStatus;
import com.supportportal.service.FileStorageService;
import com.supportportal.service.TicketService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.core.io.Resource;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;

@RestController
@RequestMapping("/tickets")
@RequiredArgsConstructor
public class TicketController {

    private final TicketService ticketService;
    private final FileStorageService fileStorageService;

    @PostMapping(consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<ApiResponse<TicketResponse>> createTicket(
            @AuthenticationPrincipal User user,
            @Valid @RequestPart("ticket") TicketCreateRequest request,
            @RequestPart(value = "files", required = false) List<MultipartFile> files) {
        return ResponseEntity.ok(ApiResponse.success("Ticket created successfully",
                ticketService.createTicket(request, files, user)));
    }

    @GetMapping
    public ResponseEntity<ApiResponse<Page<TicketResponse>>> getMyTickets(
            @AuthenticationPrincipal User user,
            @RequestParam(required = false) String search,
            @RequestParam(required = false) TicketStatus status,
            @RequestParam(required = false) TicketPriority priority,
            @RequestParam(required = false) TicketCategory category,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "10") int size,
            @RequestParam(defaultValue = "createdAt") String sortBy,
            @RequestParam(defaultValue = "desc") String sortDir) {
        Sort sort = sortDir.equalsIgnoreCase("asc") ?
                Sort.by(sortBy).ascending() : Sort.by(sortBy).descending();
        return ResponseEntity.ok(ApiResponse.success(
                ticketService.getUserTickets(user, search, status, priority, category,
                        PageRequest.of(page, size, sort))));
    }

    @GetMapping("/{id}")
    public ResponseEntity<ApiResponse<TicketResponse>> getTicketById(
            @AuthenticationPrincipal User user,
            @PathVariable Long id) {
        return ResponseEntity.ok(ApiResponse.success(ticketService.getTicketById(id, user)));
    }

    @GetMapping("/number/{ticketNumber}")
    public ResponseEntity<ApiResponse<TicketResponse>> getTicketByNumber(
            @AuthenticationPrincipal User user,
            @PathVariable String ticketNumber) {
        return ResponseEntity.ok(ApiResponse.success(ticketService.getTicketByNumber(ticketNumber, user)));
    }

    @GetMapping("/{ticketId}/messages")
    public ResponseEntity<ApiResponse<List<ChatMessageResponse>>> getMessages(
            @AuthenticationPrincipal User user,
            @PathVariable Long ticketId) {
        return ResponseEntity.ok(ApiResponse.success(ticketService.getTicketMessages(ticketId, user)));
    }

    @PostMapping("/{ticketId}/messages")
    public ResponseEntity<ApiResponse<ChatMessageResponse>> sendMessage(
            @AuthenticationPrincipal User user,
            @PathVariable Long ticketId,
            @Valid @RequestBody ChatMessageRequest request) {
        return ResponseEntity.ok(ApiResponse.success("Message sent",
                ticketService.addChatMessage(ticketId, request, user)));
    }

    @GetMapping("/attachments/{attachmentId}/download")
    public ResponseEntity<Resource> downloadAttachment(
            @AuthenticationPrincipal User user,
            @PathVariable Long attachmentId) {
        Resource resource = fileStorageService.loadFileAsResource(attachmentId);
        return ResponseEntity.ok()
                .header(HttpHeaders.CONTENT_DISPOSITION,
                        "attachment; filename=\"" + resource.getFilename() + "\"")
                .contentType(MediaType.APPLICATION_OCTET_STREAM)
                .body(resource);
    }
}
