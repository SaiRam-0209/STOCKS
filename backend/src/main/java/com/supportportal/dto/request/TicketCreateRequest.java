package com.supportportal.dto.request;

import com.supportportal.enums.TicketCategory;
import com.supportportal.enums.TicketPriority;
import jakarta.validation.constraints.*;
import lombok.Data;

@Data
public class TicketCreateRequest {

    @NotBlank(message = "Subject is required")
    @Size(min = 5, max = 200, message = "Subject must be between 5 and 200 characters")
    @Pattern(regexp = "^[a-zA-Z0-9\\s.,!?'\"()-]+$",
             message = "Subject contains invalid characters. Please use letters, numbers, and common punctuation only")
    private String subject;

    @NotBlank(message = "Description is required")
    @Size(min = 20, max = 5000, message = "Description must be between 20 and 5000 characters")
    private String description;

    @NotNull(message = "Category is required")
    private TicketCategory category;

    @NotNull(message = "Priority is required")
    private TicketPriority priority;
}
