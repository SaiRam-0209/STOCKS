package com.supportportal.dto.request;

import com.supportportal.enums.AgentType;
import com.supportportal.enums.TicketStatus;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

@Data
public class TicketUpdateRequest {

    @NotNull(message = "Status is required")
    private TicketStatus status;

    private Long assignedToId;

    private AgentType assignedAgentType;

    private String adminNote;
}
