package com.supportportal.service;

import com.itextpdf.text.*;
import com.itextpdf.text.pdf.PdfPCell;
import com.itextpdf.text.pdf.PdfPTable;
import com.itextpdf.text.pdf.PdfWriter;
import com.supportportal.entity.Ticket;
import com.supportportal.enums.TicketCategory;
import com.supportportal.enums.TicketPriority;
import com.supportportal.enums.TicketStatus;
import com.supportportal.repository.TicketRepository;
import lombok.RequiredArgsConstructor;
import org.apache.commons.csv.CSVFormat;
import org.apache.commons.csv.CSVPrinter;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.PrintWriter;
import java.time.format.DateTimeFormatter;
import java.util.List;

@Service
@RequiredArgsConstructor
public class ReportService {

    private final TicketRepository ticketRepository;
    private static final DateTimeFormatter FORMATTER = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm");

    public byte[] exportTicketsCSV(TicketStatus status, TicketPriority priority, TicketCategory category) throws IOException {
        List<Ticket> tickets = ticketRepository.filterTickets(null, status, priority, category, null,
                Pageable.unpaged()).getContent();

        ByteArrayOutputStream out = new ByteArrayOutputStream();
        CSVPrinter printer = new CSVPrinter(new PrintWriter(out),
                CSVFormat.DEFAULT.withHeader(
                        "Ticket Number", "Subject", "Category", "Priority", "Status",
                        "User Name", "User Email", "Assigned To", "Created At", "Updated At", "Resolved At"));

        for (Ticket t : tickets) {
            printer.printRecord(
                    t.getTicketNumber(),
                    t.getSubject(),
                    t.getCategory().name(),
                    t.getPriority().name(),
                    t.getStatus().name(),
                    t.getUser().getName(),
                    t.getUser().getEmail(),
                    t.getAssignedTo() != null ? t.getAssignedTo().getName() : "Unassigned",
                    t.getCreatedAt() != null ? FORMATTER.format(t.getCreatedAt()) : "",
                    t.getUpdatedAt() != null ? FORMATTER.format(t.getUpdatedAt()) : "",
                    t.getResolvedAt() != null ? FORMATTER.format(t.getResolvedAt()) : "N/A"
            );
        }
        printer.flush();
        return out.toByteArray();
    }

    public byte[] exportTicketsPDF(TicketStatus status, TicketPriority priority, TicketCategory category) throws DocumentException {
        List<Ticket> tickets = ticketRepository.filterTickets(null, status, priority, category, null,
                Pageable.unpaged()).getContent();

        ByteArrayOutputStream out = new ByteArrayOutputStream();
        Document document = new Document(PageSize.A4.rotate());
        PdfWriter.getInstance(document, out);
        document.open();

        // Title
        Font titleFont = new Font(Font.FontFamily.HELVETICA, 18, Font.BOLD, new BaseColor(33, 33, 33));
        Paragraph title = new Paragraph("Ticket Report - AI Support Portal", titleFont);
        title.setAlignment(Element.ALIGN_CENTER);
        title.setSpacingAfter(20);
        document.add(title);

        // Subtitle
        Font subFont = new Font(Font.FontFamily.HELVETICA, 10, Font.NORMAL, BaseColor.GRAY);
        Paragraph sub = new Paragraph("Generated on: " + java.time.LocalDateTime.now().format(FORMATTER) +
                " | Total Tickets: " + tickets.size(), subFont);
        sub.setAlignment(Element.ALIGN_CENTER);
        sub.setSpacingAfter(20);
        document.add(sub);

        // Table
        PdfPTable table = new PdfPTable(8);
        table.setWidthPercentage(100);
        table.setWidths(new float[]{1.5f, 2.5f, 1.2f, 1.0f, 1.0f, 1.5f, 1.5f, 1.5f});

        String[] headers = {"Ticket #", "Subject", "Category", "Priority", "Status", "User", "Assigned To", "Created At"};
        Font headerFont = new Font(Font.FontFamily.HELVETICA, 9, Font.BOLD, BaseColor.WHITE);
        BaseColor headerBg = new BaseColor(63, 81, 181);

        for (String h : headers) {
            PdfPCell cell = new PdfPCell(new Phrase(h, headerFont));
            cell.setBackgroundColor(headerBg);
            cell.setPadding(8);
            cell.setHorizontalAlignment(Element.ALIGN_CENTER);
            table.addCell(cell);
        }

        Font cellFont = new Font(Font.FontFamily.HELVETICA, 8);
        boolean alt = false;
        for (Ticket t : tickets) {
            BaseColor bg = alt ? new BaseColor(245, 245, 245) : BaseColor.WHITE;
            addCell(table, t.getTicketNumber(), cellFont, bg);
            addCell(table, t.getSubject().length() > 30 ? t.getSubject().substring(0, 30) + "..." : t.getSubject(), cellFont, bg);
            addCell(table, t.getCategory().name(), cellFont, bg);
            addCell(table, t.getPriority().name(), cellFont, bg);
            addCell(table, t.getStatus().name(), cellFont, bg);
            addCell(table, t.getUser().getName(), cellFont, bg);
            addCell(table, t.getAssignedTo() != null ? t.getAssignedTo().getName() : "Unassigned", cellFont, bg);
            addCell(table, t.getCreatedAt() != null ? FORMATTER.format(t.getCreatedAt()) : "", cellFont, bg);
            alt = !alt;
        }

        document.add(table);
        document.close();
        return out.toByteArray();
    }

    private void addCell(PdfPTable table, String text, Font font, BaseColor bg) {
        PdfPCell cell = new PdfPCell(new Phrase(text, font));
        cell.setBackgroundColor(bg);
        cell.setPadding(6);
        cell.setVerticalAlignment(Element.ALIGN_MIDDLE);
        table.addCell(cell);
    }
}
