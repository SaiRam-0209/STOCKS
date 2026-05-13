package com.supportportal.service;

import com.supportportal.dto.request.ChatMessageRequest;
import com.supportportal.dto.request.TicketCreateRequest;
import com.supportportal.dto.request.TicketUpdateRequest;
import com.supportportal.dto.response.*;
import com.supportportal.entity.*;
import com.supportportal.enums.*;
import com.supportportal.exception.BadRequestException;
import com.supportportal.exception.ResourceNotFoundException;
import com.supportportal.repository.*;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.List;
import java.util.concurrent.atomic.AtomicLong;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class TicketService {

    private final TicketRepository ticketRepository;
    private final ChatMessageRepository chatMessageRepository;
    private final AIResponseRepository aiResponseRepository;
    private final AttachmentRepository attachmentRepository;
    private final UserRepository userRepository;
    private final FileStorageService fileStorageService;
    private final AIService aiService;
    private final EmailService emailService;
    private final NotificationService notificationService;
    private final AuditLogService auditLogService;
    private final SimpMessagingTemplate messagingTemplate;

    private static final AtomicLong ticketCounter = new AtomicLong(1000);

    @Transactional
    public TicketResponse createTicket(TicketCreateRequest request, List<MultipartFile> files, User user) {
        String ticketNumber = generateTicketNumber();

        Ticket ticket = Ticket.builder()
                .ticketNumber(ticketNumber)
                .user(user)
                .category(request.getCategory())
                .priority(request.getPriority())
                .status(TicketStatus.OPEN)
                .subject(request.getSubject().trim())
                .description(request.getDescription().trim())
                .build();

        ticketRepository.save(ticket);

        // Handle file attachments
        if (files != null && !files.isEmpty()) {
            files.forEach(file -> {
                if (!file.isEmpty()) {
                    AttachmentResponse att = fileStorageService.storeFile(file, ticket, user);
                    // attachment saved inside storeFile
                }
            });
        }

        // Generate AI summary asynchronously
        aiService.generateSummaryAsync(ticket);

        // Generate AI response
        aiService.generateResponseAsync(ticket);

        // Send notifications
        emailService.sendTicketCreatedEmail(user, ticket);
        notificationService.createNotification(user, "Ticket Created",
                "Your ticket " + ticketNumber + " has been successfully created.",
                NotificationType.TICKET_CREATED, ticket);

        // Notify admins
        notificationService.notifyAdmins("New Ticket", "New ticket " + ticketNumber + " has been raised.",
                NotificationType.TICKET_CREATED, ticket);

        auditLogService.log(user, "TICKET_CREATED", "Ticket", ticket.getId(),
                "Ticket created: " + ticketNumber, null);

        return mapToResponse(ticket, true);
    }

    public Page<TicketResponse> getUserTickets(User user, String search, TicketStatus status,
                                               TicketPriority priority, TicketCategory category,
                                               Pageable pageable) {
        return ticketRepository.filterUserTickets(user, search, status, priority, category, pageable)
                .map(t -> mapToResponse(t, false));
    }

    public Page<TicketResponse> getAllTickets(String search, TicketStatus status,
                                              TicketPriority priority, TicketCategory category,
                                              Long userId, Pageable pageable) {
        return ticketRepository.filterTickets(search, status, priority, category, userId, pageable)
                .map(t -> mapToResponse(t, false));
    }

    public TicketResponse getTicketById(Long id, User currentUser) {
        Ticket ticket = ticketRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Ticket not found with id: " + id));

        if (currentUser.getRole() == UserRole.USER && !ticket.getUser().getId().equals(currentUser.getId())) {
            throw new BadRequestException("You do not have permission to view this ticket.");
        }

        return mapToResponse(ticket, true);
    }

    public TicketResponse getTicketByNumber(String ticketNumber, User currentUser) {
        Ticket ticket = ticketRepository.findByTicketNumber(ticketNumber)
                .orElseThrow(() -> new ResourceNotFoundException("Ticket not found: " + ticketNumber));

        if (currentUser.getRole() == UserRole.USER && !ticket.getUser().getId().equals(currentUser.getId())) {
            throw new BadRequestException("You do not have permission to view this ticket.");
        }

        return mapToResponse(ticket, true);
    }

    @Transactional
    public TicketResponse updateTicketStatus(Long id, TicketUpdateRequest request, User admin) {
        Ticket ticket = ticketRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Ticket not found with id: " + id));

        TicketStatus oldStatus = ticket.getStatus();
        ticket.setStatus(request.getStatus());

        if (request.getAssignedToId() != null) {
            User assignedUser = userRepository.findById(request.getAssignedToId())
                    .orElseThrow(() -> new ResourceNotFoundException("Assigned user not found"));
            ticket.setAssignedTo(assignedUser);
            ticket.setAssignedAgentType(request.getAssignedAgentType() != null ?
                    request.getAssignedAgentType() : AgentType.HUMAN);
        }

        if (request.getAssignedAgentType() != null) {
            ticket.setAssignedAgentType(request.getAssignedAgentType());
        }

        if (request.getStatus() == TicketStatus.RESOLVED || request.getStatus() == TicketStatus.CLOSED) {
            ticket.setResolvedAt(LocalDateTime.now());
        }

        ticketRepository.save(ticket);

        // Send status update notifications
        emailService.sendTicketStatusUpdateEmail(ticket.getUser(), ticket, oldStatus);
        notificationService.createNotification(ticket.getUser(),
                "Ticket Status Updated",
                "Your ticket " + ticket.getTicketNumber() + " status changed from " +
                        oldStatus + " to " + request.getStatus(),
                NotificationType.TICKET_UPDATED, ticket);

        // If there's an admin note, add as chat message
        if (request.getAdminNote() != null && !request.getAdminNote().isBlank()) {
            ChatMessage chatMessage = ChatMessage.builder()
                    .ticket(ticket)
                    .sender(admin)
                    .message(request.getAdminNote())
                    .messageType(MessageType.ADMIN_REPLY)
                    .isAiGenerated(false)
                    .build();
            chatMessageRepository.save(chatMessage);
        }

        auditLogService.log(admin, "TICKET_STATUS_UPDATED", "Ticket", ticket.getId(),
                "Status changed from " + oldStatus + " to " + request.getStatus(), null);

        // Real-time notification via WebSocket
        messagingTemplate.convertAndSendToUser(
                ticket.getUser().getEmail(), "/queue/notifications",
                "Your ticket " + ticket.getTicketNumber() + " has been updated.");

        return mapToResponse(ticket, true);
    }

    @Transactional
    public ChatMessageResponse addChatMessage(Long ticketId, ChatMessageRequest request, User sender) {
        Ticket ticket = ticketRepository.findById(ticketId)
                .orElseThrow(() -> new ResourceNotFoundException("Ticket not found"));

        if (sender.getRole() == UserRole.USER && !ticket.getUser().getId().equals(sender.getId())) {
            throw new BadRequestException("You cannot send messages to this ticket.");
        }

        if (ticket.getStatus() == TicketStatus.CLOSED) {
            throw new BadRequestException("Cannot send messages to a closed ticket.");
        }

        MessageType msgType = sender.getRole() == UserRole.ADMIN ?
                MessageType.ADMIN_REPLY : MessageType.USER_MESSAGE;

        ChatMessage message = ChatMessage.builder()
                .ticket(ticket)
                .sender(sender)
                .message(request.getMessage().trim())
                .messageType(msgType)
                .isAiGenerated(false)
                .build();

        chatMessageRepository.save(message);

        // Notify the other party
        User recipient = sender.getRole() == UserRole.ADMIN ? ticket.getUser() : null;
        if (recipient != null) {
            notificationService.createNotification(recipient,
                    "New Message on Ticket " + ticket.getTicketNumber(),
                    sender.getName() + " replied to your ticket.",
                    NotificationType.NEW_MESSAGE, ticket);

            messagingTemplate.convertAndSendToUser(
                    recipient.getEmail(), "/queue/notifications",
                    "New message on ticket " + ticket.getTicketNumber());
        }

        return mapMessageToResponse(message);
    }

    public List<ChatMessageResponse> getTicketMessages(Long ticketId, User currentUser) {
        Ticket ticket = ticketRepository.findById(ticketId)
                .orElseThrow(() -> new ResourceNotFoundException("Ticket not found"));

        if (currentUser.getRole() == UserRole.USER && !ticket.getUser().getId().equals(currentUser.getId())) {
            throw new BadRequestException("Access denied.");
        }

        return chatMessageRepository.findByTicketIdOrderByCreatedAtAsc(ticketId)
                .stream().map(this::mapMessageToResponse).collect(Collectors.toList());
    }

    private String generateTicketNumber() {
        String datePart = LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyyMMdd"));
        long count = ticketRepository.count() + ticketCounter.incrementAndGet();
        return "TKT-" + datePart + "-" + String.format("%04d", count % 10000);
    }

    public TicketResponse mapToResponse(Ticket ticket, boolean includeDetails) {
        TicketResponse.TicketResponseBuilder builder = TicketResponse.builder()
                .id(ticket.getId())
                .ticketNumber(ticket.getTicketNumber())
                .userId(ticket.getUser().getId())
                .userName(ticket.getUser().getName())
                .userEmail(ticket.getUser().getEmail())
                .category(ticket.getCategory())
                .priority(ticket.getPriority())
                .status(ticket.getStatus())
                .subject(ticket.getSubject())
                .description(ticket.getDescription())
                .aiSummary(ticket.getAiSummary())
                .assignedAgentType(ticket.getAssignedAgentType())
                .resolvedAt(ticket.getResolvedAt())
                .createdAt(ticket.getCreatedAt())
                .updatedAt(ticket.getUpdatedAt());

        if (ticket.getAssignedTo() != null) {
            builder.assignedToId(ticket.getAssignedTo().getId())
                   .assignedToName(ticket.getAssignedTo().getName());
        }

        if (includeDetails) {
            List<AttachmentResponse> attachments = attachmentRepository.findByTicketId(ticket.getId())
                    .stream().map(this::mapAttachmentToResponse).collect(Collectors.toList());

            List<ChatMessageResponse> messages = chatMessageRepository
                    .findByTicketIdOrderByCreatedAtAsc(ticket.getId())
                    .stream().map(this::mapMessageToResponse).collect(Collectors.toList());

            List<AIResponseDto> aiResponses = aiResponseRepository
                    .findByTicketIdOrderByCreatedAtDesc(ticket.getId())
                    .stream().map(this::mapAIResponseToDto).collect(Collectors.toList());

            builder.attachments(attachments)
                   .chatMessages(messages)
                   .aiResponses(aiResponses)
                   .messageCount(messages.size());
        } else {
            builder.messageCount((int) chatMessageRepository.countByTicketId(ticket.getId()));
        }

        return builder.build();
    }

    public ChatMessageResponse mapMessageToResponse(ChatMessage message) {
        return ChatMessageResponse.builder()
                .id(message.getId())
                .ticketId(message.getTicket().getId())
                .senderId(message.getSender().getId())
                .senderName(message.getSender().getName())
                .senderRole(message.getSender().getRole().name())
                .message(message.getMessage())
                .messageType(message.getMessageType())
                .isAiGenerated(message.getIsAiGenerated())
                .createdAt(message.getCreatedAt())
                .build();
    }

    private AttachmentResponse mapAttachmentToResponse(Attachment attachment) {
        return AttachmentResponse.builder()
                .id(attachment.getId())
                .fileName(attachment.getFileName())
                .originalName(attachment.getOriginalName())
                .fileSize(attachment.getFileSize())
                .fileType(attachment.getFileType())
                .downloadUrl("/attachments/" + attachment.getId() + "/download")
                .createdAt(attachment.getCreatedAt())
                .build();
    }

    private AIResponseDto mapAIResponseToDto(AIResponse ai) {
        return AIResponseDto.builder()
                .id(ai.getId())
                .ticketId(ai.getTicket().getId())
                .response(ai.getResponse())
                .confidenceScore(ai.getConfidenceScore())
                .status(ai.getStatus())
                .reviewedByName(ai.getReviewedBy() != null ? ai.getReviewedBy().getName() : null)
                .reviewedAt(ai.getReviewedAt())
                .rejectionReason(ai.getRejectionReason())
                .createdAt(ai.getCreatedAt())
                .build();
    }
}
