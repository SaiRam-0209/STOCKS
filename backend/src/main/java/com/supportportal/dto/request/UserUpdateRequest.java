package com.supportportal.dto.request;

import jakarta.validation.constraints.*;
import lombok.Data;

@Data
public class UserUpdateRequest {

    @NotBlank(message = "Full name is required")
    @Size(min = 2, max = 100, message = "Name must be between 2 and 100 characters")
    @Pattern(regexp = "^[a-zA-Z\\s'-]+$", message = "Name can only contain letters, spaces, hyphens, and apostrophes")
    private String name;

    @Pattern(regexp = "^[+]?[0-9]{10,15}$", message = "Please provide a valid phone number")
    private String phone;

    @Size(max = 100, message = "Department must not exceed 100 characters")
    private String department;
}
