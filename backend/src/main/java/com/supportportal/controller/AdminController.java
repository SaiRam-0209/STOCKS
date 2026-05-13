package com.supportportal.controller;

import com.supportportal.dto.request.*;
import com.supportportal.dto.response.*;
import com.supportportal.entity.User;
import com.supportportal.enums.*;
import com.supportportal.service.*;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/admin")
@RequiredArgsConstructor
@PreAuthorize("hasRole('ADMIN')")
public class AdminController {

    private final TicketService ticketService;
    private final UserService userService;
    private final AIService aiService;
    private final AuditLogService auditLogService;
    private final AnalyticsService analyticsService;

    // ===================== TICKET MANAGEMENT =====================
    @GetMapping("/tickets")
    public ResponseEntity<ApiResponse<Page<TicketResponse>>> getAllTickets(
            @RequestParam(required = false) String search,
            @RequestParam(required = false) TicketStatus status,
            @RequestParam(required = false) TicketPriority priority,
            @RequestParam(required = false) TicketCategory category,
            @RequestParam(required = false) Long userId,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "10") int size,
            @RequestParam(defaultValue = "createdAt") String sortBy,
            @RequestParam(defaultValue = "desc") String sortDir) {
        Sort sort = sortDir.equalsIgnoreCase("asc") ?
                Sort.by(sortBy).ascending() : Sort.by(sortBy).descending();
        return ResponseEntity.ok(ApiResponse.success(
                ticketService.getAllTickets(search, status, priority, category, userId,
                        PageRequest.of(page, size, sort))));
    }

    @GetMapping("/tickets/{id}")
    public ResponseEntity<ApiResponse<TicketResponse>> getTicketById(
            @AuthenticationPrincipal User admin,
            @PathVariable Long id) {
        return ResponseEntity.ok(ApiResponse.success(ticketService.getTicketById(id, admin)));
    }

    @PutMapping("/tickets/{id}/status")
    public ResponseEntity<ApiResponse<TicketResponse>> updateTicketStatus(
            @AuthenticationPrincipal User admin,
            @PathVariable Long id,
            @Valid @RequestBody TicketUpdateRequest request) {
        return ResponseEntity.ok(ApiResponse.success("Ticket updated successfully",
                ticketService.updateTicketStatus(id, request, admin)));
    }

    @PostMapping("/tickets/{ticketId}/messages")
    public ResponseEntity<ApiResponse<ChatMessageResponse>> sendMessage(
            @AuthenticationPrincipal User admin,
            @PathVariable Long ticketId,
            @Valid @RequestBody ChatMessageRequest request) {
        return ResponseEntity.ok(ApiResponse.success("Message sent",
                ticketService.addChatMessage(ticketId, request, admin)));
    }

    // ===================== AI RESPONSE MANAGEMENT =====================
    @GetMapping("/ai-responses/pending")
    public ResponseEntity<ApiResponse<Page<AIResponseDto>>> getPendingAIResponses(
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "10") int size) {
        return ResponseEntity.ok(ApiResponse.success(
                aiService.getPendingAIResponses(PageRequest.of(page, size))));
    }

    @PutMapping("/ai-responses/{id}/review")
    public ResponseEntity<ApiResponse<AIResponseDto>> reviewAIResponse(
            @AuthenticationPrincipal User admin,
            @PathVariable Long id,
            @Valid @RequestBody AIResponseReviewRequest request) {
        return ResponseEntity.ok(ApiResponse.success("AI response reviewed",
                aiService.reviewAIResponse(id, request, admin)));
    }

    // ===================== USER MANAGEMENT =====================
    @GetMapping("/users")
    public ResponseEntity<ApiResponse<Page<UserResponse>>> getAllUsers(
            @RequestParam(required = false) String search,
            @RequestParam(required = false) UserRole role,
            @RequestParam(required = false) Boolean isActive,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "10") int size) {
        return ResponseEntity.ok(ApiResponse.success(
                userService.getAllUsers(search, role, isActive, PageRequest.of(page, size))));
    }

    @GetMapping("/users/{id}")
    public ResponseEntity<ApiResponse<UserResponse>> getUserById(@PathVariable Long id) {
        return ResponseEntity.ok(ApiResponse.success(userService.getUserById(id)));
    }

    @PostMapping("/users")
    public ResponseEntity<ApiResponse<UserResponse>> createUser(
            @AuthenticationPrincipal User admin,
            @Valid @RequestBody RegisterRequest request) {
        return ResponseEntity.ok(ApiResponse.success("User created successfully",
                userService.createUser(request, admin)));
    }

    @PutMapping("/users/{id}/toggle-status")
    public ResponseEntity<ApiResponse<UserResponse>> toggleUserStatus(
            @AuthenticationPrincipal User admin,
            @PathVariable Long id) {
        return ResponseEntity.ok(ApiResponse.success("User status updated",
                userService.toggleUserStatus(id, admin)));
    }

    @DeleteMapping("/users/{id}")
    public ResponseEntity<ApiResponse<Void>> deleteUser(
            @AuthenticationPrincipal User admin,
            @PathVariable Long id) {
        userService.deleteUser(id, admin);
        return ResponseEntity.ok(ApiResponse.success("User deleted successfully", null));
    }

    // ===================== AUDIT LOGS =====================
    @GetMapping("/audit-logs")
    public ResponseEntity<ApiResponse<Page<AuditLogResponse>>> getAuditLogs(
            @RequestParam(required = false) String search,
            @RequestParam(required = false) Long userId,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size) {
        return ResponseEntity.ok(ApiResponse.success(
                auditLogService.getAuditLogs(search, userId, PageRequest.of(page, size,
                        Sort.by("createdAt").descending()))));
    }

    // ===================== ANALYTICS =====================
    @GetMapping("/analytics")
    public ResponseEntity<ApiResponse<AnalyticsResponse>> getAnalytics() {
        return ResponseEntity.ok(ApiResponse.success(analyticsService.getAnalytics()));
    }
}
