package com.supportportal.service;

import com.supportportal.dto.response.AttachmentResponse;
import com.supportportal.entity.Attachment;
import com.supportportal.entity.Ticket;
import com.supportportal.entity.User;
import com.supportportal.exception.BadRequestException;
import com.supportportal.repository.AttachmentRepository;
import jakarta.annotation.PostConstruct;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.Resource;
import org.springframework.core.io.UrlResource;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.net.MalformedURLException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardCopyOption;
import java.util.Arrays;
import java.util.List;
import java.util.UUID;

@Service
@RequiredArgsConstructor
@Slf4j
public class FileStorageService {

    private final AttachmentRepository attachmentRepository;

    @Value("${app.upload.directory}")
    private String uploadDir;

    @Value("${app.upload.allowed-types}")
    private String allowedTypes;

    private Path uploadPath;

    private static final long MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB

    @PostConstruct
    public void init() {
        uploadPath = Paths.get(uploadDir).toAbsolutePath().normalize();
        try {
            Files.createDirectories(uploadPath);
        } catch (IOException e) {
            throw new RuntimeException("Could not create upload directory: " + uploadDir, e);
        }
    }

    public AttachmentResponse storeFile(MultipartFile file, Ticket ticket, User uploader) {
        validateFile(file);

        String originalFileName = StringUtils.cleanPath(file.getOriginalFilename());
        String extension = getFileExtension(originalFileName);
        String uniqueFileName = UUID.randomUUID() + "." + extension;

        try {
            Path targetLocation = uploadPath.resolve(uniqueFileName);
            Files.copy(file.getInputStream(), targetLocation, StandardCopyOption.REPLACE_EXISTING);

            Attachment attachment = Attachment.builder()
                    .ticket(ticket)
                    .fileName(uniqueFileName)
                    .originalName(originalFileName)
                    .filePath(targetLocation.toString())
                    .fileSize(file.getSize())
                    .fileType(file.getContentType())
                    .uploadedBy(uploader)
                    .build();

            attachmentRepository.save(attachment);
            log.info("File stored: {} for ticket: {}", uniqueFileName, ticket.getTicketNumber());

            return AttachmentResponse.builder()
                    .id(attachment.getId())
                    .fileName(uniqueFileName)
                    .originalName(originalFileName)
                    .fileSize(file.getSize())
                    .fileType(file.getContentType())
                    .downloadUrl("/attachments/" + attachment.getId() + "/download")
                    .build();
        } catch (IOException ex) {
            throw new BadRequestException("Could not store file " + originalFileName + ". Please try again.");
        }
    }

    public Resource loadFileAsResource(Long attachmentId) {
        Attachment attachment = attachmentRepository.findById(attachmentId)
                .orElseThrow(() -> new BadRequestException("File not found"));

        try {
            Path filePath = Paths.get(attachment.getFilePath()).normalize();
            Resource resource = new UrlResource(filePath.toUri());
            if (resource.exists()) {
                return resource;
            }
            throw new BadRequestException("File not found: " + attachment.getOriginalName());
        } catch (MalformedURLException ex) {
            throw new BadRequestException("File not found: " + attachment.getOriginalName());
        }
    }

    private void validateFile(MultipartFile file) {
        if (file.isEmpty()) {
            throw new BadRequestException("Cannot upload an empty file.");
        }

        if (file.getSize() > MAX_FILE_SIZE) {
            throw new BadRequestException("File size exceeds the maximum limit of 10MB.");
        }

        String originalFileName = file.getOriginalFilename();
        if (originalFileName == null || originalFileName.isBlank()) {
            throw new BadRequestException("File name is invalid.");
        }

        if (originalFileName.contains("..")) {
            throw new BadRequestException("File name contains invalid path sequence.");
        }

        String extension = getFileExtension(originalFileName).toLowerCase();
        List<String> allowed = Arrays.asList(allowedTypes.split(","));
        if (!allowed.contains(extension)) {
            throw new BadRequestException("File type '" + extension + "' is not allowed. " +
                    "Allowed types: " + allowedTypes);
        }
    }

    private String getFileExtension(String fileName) {
        int dotIndex = fileName.lastIndexOf('.');
        if (dotIndex < 0) {
            throw new BadRequestException("File must have an extension.");
        }
        return fileName.substring(dotIndex + 1);
    }
}
