package com.supportportal.dto.response;

import com.supportportal.enums.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.List;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class TicketResponse {
    private Long id;
    private String ticketNumber;
    private Long userId;
    private String userName;
    private String userEmail;
    private Long assignedToId;
    private String assignedToName;
    private TicketCategory category;
    private TicketPriority priority;
    private TicketStatus status;
    private String subject;
    private String description;
    private String aiSummary;
    private AgentType assignedAgentType;
    private LocalDateTime resolvedAt;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
    private List<AttachmentResponse> attachments;
    private List<ChatMessageResponse> chatMessages;
    private List<AIResponseDto> aiResponses;
    private int messageCount;
}
