package com.supportportal.dto.response;

import com.supportportal.enums.AIResponseStatus;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class AIResponseDto {
    private Long id;
    private Long ticketId;
    private String response;
    private Double confidenceScore;
    private AIResponseStatus status;
    private String reviewedByName;
    private LocalDateTime reviewedAt;
    private String rejectionReason;
    private LocalDateTime createdAt;
}
