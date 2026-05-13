package com.supportportal.service;

import com.supportportal.dto.request.AIResponseReviewRequest;
import com.supportportal.dto.response.AIResponseDto;
import com.supportportal.entity.AIResponse;
import com.supportportal.entity.ChatMessage;
import com.supportportal.entity.Ticket;
import com.supportportal.entity.User;
import com.supportportal.enums.AIResponseStatus;
import com.supportportal.enums.MessageType;
import com.supportportal.enums.NotificationType;
import com.supportportal.exception.ResourceNotFoundException;
import com.supportportal.repository.AIResponseRepository;
import com.supportportal.repository.ChatMessageRepository;
import com.supportportal.repository.TicketRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.reactive.function.client.WebClient;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

@Service
@RequiredArgsConstructor
@Slf4j
public class AIService {

    private final AIResponseRepository aiResponseRepository;
    private final TicketRepository ticketRepository;
    private final ChatMessageRepository chatMessageRepository;
    private final AuditLogService auditLogService;
    private final NotificationService notificationService;

    @Value("${ai.api.key}")
    private String apiKey;

    @Value("${ai.api.url}")
    private String apiUrl;

    @Value("${ai.model}")
    private String model;

    @Value("${ai.max-tokens}")
    private int maxTokens;

    @Value("${ai.enabled}")
    private boolean aiEnabled;

    @Async
    @Transactional
    public void generateSummaryAsync(Ticket ticket) {
        if (!aiEnabled) return;
        try {
            String summary = callAIForSummary(ticket.getSubject(), ticket.getDescription());
            ticket.setAiSummary(summary);
            ticketRepository.save(ticket);
            log.info("AI summary generated for ticket: {}", ticket.getTicketNumber());
        } catch (Exception e) {
            log.error("Failed to generate AI summary for ticket {}: {}", ticket.getTicketNumber(), e.getMessage());
        }
    }

    @Async
    @Transactional
    public void generateResponseAsync(Ticket ticket) {
        if (!aiEnabled) return;
        try {
            String response = callAIForResponse(ticket);
            double confidence = 0.85;

            AIResponse aiResponse = AIResponse.builder()
                    .ticket(ticket)
                    .response(response)
                    .confidenceScore(confidence)
                    .status(AIResponseStatus.PENDING)
                    .build();

            aiResponseRepository.save(aiResponse);

            // Notify admins about pending AI response
            notificationService.notifyAdmins(
                    "AI Response Pending Review",
                    "AI has generated a response for ticket " + ticket.getTicketNumber() + " awaiting approval.",
                    NotificationType.AI_RESPONSE, ticket);

            log.info("AI response generated for ticket: {}", ticket.getTicketNumber());
        } catch (Exception e) {
            log.error("Failed to generate AI response for ticket {}: {}", ticket.getTicketNumber(), e.getMessage());
        }
    }

    @Transactional
    public AIResponseDto reviewAIResponse(Long responseId, AIResponseReviewRequest request, User admin) {
        AIResponse aiResponse = aiResponseRepository.findById(responseId)
                .orElseThrow(() -> new ResourceNotFoundException("AI Response not found"));

        aiResponse.setStatus(request.getStatus());
        aiResponse.setReviewedBy(admin);
        aiResponse.setReviewedAt(LocalDateTime.now());

        if (request.getStatus() == AIResponseStatus.REJECTED) {
            aiResponse.setRejectionReason(request.getRejectionReason());
        }

        if (request.getStatus() == AIResponseStatus.APPROVED) {
            // Add AI response as chat message
            ChatMessage chatMessage = ChatMessage.builder()
                    .ticket(aiResponse.getTicket())
                    .sender(admin)
                    .message(aiResponse.getResponse())
                    .messageType(MessageType.AI_RESPONSE)
                    .isAiGenerated(true)
                    .build();
            chatMessageRepository.save(chatMessage);

            notificationService.createNotification(aiResponse.getTicket().getUser(),
                    "AI Response Available",
                    "An AI-generated response has been approved for your ticket " +
                            aiResponse.getTicket().getTicketNumber(),
                    NotificationType.AI_RESPONSE, aiResponse.getTicket());
        }

        aiResponseRepository.save(aiResponse);
        auditLogService.log(admin, "AI_RESPONSE_" + request.getStatus(), "AIResponse",
                responseId, "AI response " + request.getStatus().name().toLowerCase(), null);

        return mapToDto(aiResponse);
    }

    public Page<AIResponseDto> getPendingAIResponses(Pageable pageable) {
        return aiResponseRepository.findByStatus(AIResponseStatus.PENDING, pageable)
                .map(this::mapToDto);
    }

    private String callAIForSummary(String subject, String description) {
        /*
         * INCLUDE YOUR AI API KEY HERE
         * Replace the placeholder below with your actual AI API call.
         * Example using Anthropic Claude API:
         *
         * WebClient client = WebClient.builder()
         *     .baseUrl(apiUrl)
         *     .defaultHeader("x-api-key", apiKey)
         *     .defaultHeader("anthropic-version", "2023-06-01")
         *     .defaultHeader(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
         *     .build();
         *
         * Map<String, Object> requestBody = Map.of(
         *     "model", model,
         *     "max_tokens", maxTokens,
         *     "messages", List.of(Map.of(
         *         "role", "user",
         *         "content", "Summarize this support ticket in 2-3 sentences:\n\nSubject: " + subject + "\n\nDescription: " + description
         *     ))
         * );
         *
         * // Parse response and extract text
         */
        return "AI Summary: This ticket relates to '" + subject + "'. " +
                "The user has reported an issue that requires attention. " +
                "Priority handling recommended based on the description provided. " +
                "[Note: Connect your AI API key in application.properties to enable real AI summaries]";
    }

    private String callAIForResponse(Ticket ticket) {
        /*
         * INCLUDE YOUR AI API KEY HERE
         * This method should call your preferred AI API to generate a support response.
         * Configure ai.api.key in application.properties with your actual API key.
         *
         * Supported APIs:
         * - Anthropic Claude: https://api.anthropic.com/v1/messages
         * - OpenAI: https://api.openai.com/v1/chat/completions
         * - Any compatible LLM API
         */
        return "Thank you for contacting our support team regarding \"" + ticket.getSubject() + "\". " +
                "We have received your request and our team is reviewing it. " +
                "Based on the category (" + ticket.getCategory() + ") and priority (" + ticket.getPriority() + "), " +
                "we will ensure this is handled promptly. " +
                "We will update you as soon as we have more information. " +
                "[Note: This is a placeholder. Configure your AI API key for real AI responses]";
    }

    private AIResponseDto mapToDto(AIResponse ai) {
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
