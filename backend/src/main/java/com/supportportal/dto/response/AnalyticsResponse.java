package com.supportportal.dto.response;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;
import java.util.Map;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class AnalyticsResponse {
    private long totalTickets;
    private long openTickets;
    private long inProgressTickets;
    private long resolvedTickets;
    private long closedTickets;
    private long pendingTickets;
    private long totalUsers;
    private long activeUsers;
    private long newTicketsToday;
    private long newTicketsThisWeek;
    private long newTicketsThisMonth;
    private Double averageResolutionTimeHours;
    private long pendingAIResponses;
    private long approvedAIResponses;
    private long rejectedAIResponses;
    private Map<String, Long> ticketsByStatus;
    private Map<String, Long> ticketsByPriority;
    private Map<String, Long> ticketsByCategory;
    private List<Map<String, Object>> ticketsTrend;
    private double resolutionRate;
    private double aiApprovalRate;
}
