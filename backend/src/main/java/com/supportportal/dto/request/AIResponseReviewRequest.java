package com.supportportal.dto.request;

import com.supportportal.enums.AIResponseStatus;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

@Data
public class AIResponseReviewRequest {

    @NotNull(message = "Status is required")
    private AIResponseStatus status;

    private String rejectionReason;
}
