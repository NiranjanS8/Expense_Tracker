package com.expensetracker.export.service;

import com.expensetracker.expense.dto.ExpenseQueryParams;
import com.expensetracker.expense.dto.ExpenseResponse;
import com.expensetracker.export.entity.ExpenseExportJobType;
import com.expensetracker.expense.service.ExpenseQueryService;
import com.expensetracker.user.entity.User;
import com.lowagie.text.Document;
import com.lowagie.text.DocumentException;
import com.lowagie.text.FontFactory;
import com.lowagie.text.Paragraph;
import com.lowagie.text.Phrase;
import com.lowagie.text.Table;
import com.lowagie.text.pdf.PdfWriter;
import org.springframework.stereotype.Service;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.time.LocalDate;
import java.util.List;

@Service
public class ExpenseExportService {

    private final ExpenseQueryService expenseQueryService;

    public ExpenseExportService(ExpenseQueryService expenseQueryService) {
        this.expenseQueryService = expenseQueryService;
    }

    public byte[] exportExpensesAsCsv(User user, ExpenseQueryParams queryParams) {
        List<ExpenseResponse> expenses = expenseQueryService.getExpensesForExport(user, queryParams);

        StringBuilder csvBuilder = new StringBuilder();
        csvBuilder.append("Id,Date,Category,Amount,Payment Method,Description").append('\n');

        for (ExpenseResponse expense : expenses) {
            csvBuilder.append(expense.id()).append(',')
                    .append(expense.expenseDate()).append(',')
                    .append(escapeCsv(expense.categoryName())).append(',')
                    .append(expense.amount()).append(',')
                    .append(expense.paymentMethod()).append(',')
                    .append(escapeCsv(expense.description()))
                    .append('\n');
        }

        return csvBuilder.toString().getBytes(StandardCharsets.UTF_8);
    }

    public byte[] exportExpensesAsPdf(User user, ExpenseQueryParams queryParams) {
        List<ExpenseResponse> expenses = expenseQueryService.getExpensesForExport(user, queryParams);
        BigDecimal totalAmount = expenses.stream()
                .map(ExpenseResponse::amount)
                .reduce(BigDecimal.ZERO, BigDecimal::add);

        try (ByteArrayOutputStream outputStream = new ByteArrayOutputStream()) {
            Document document = new Document();
            PdfWriter.getInstance(document, outputStream);
            document.open();

            Paragraph title = new Paragraph("Expense Report", FontFactory.getFont(FontFactory.HELVETICA_BOLD, 16));
            title.setSpacingAfter(10f);
            document.add(title);

            document.add(new Paragraph("Generated on: " + LocalDate.now()));
            document.add(new Paragraph("Total expenses: " + expenses.size()));
            document.add(new Paragraph("Total amount: " + totalAmount));
            document.add(new Paragraph(" "));

            Table table = new Table(5);
            table.setWidth(100f);
            table.addCell(new Phrase("Date"));
            table.addCell(new Phrase("Category"));
            table.addCell(new Phrase("Amount"));
            table.addCell(new Phrase("Payment"));
            table.addCell(new Phrase("Description"));

            for (ExpenseResponse expense : expenses) {
                table.addCell(expense.expenseDate().toString());
                table.addCell(expense.categoryName());
                table.addCell(expense.amount().toString());
                table.addCell(expense.paymentMethod().name());
                table.addCell(expense.description() == null ? "" : expense.description());
            }

            document.add(table);
            document.close();
            return outputStream.toByteArray();
        } catch (DocumentException | IOException exception) {
            throw new IllegalStateException("Failed to generate PDF report", exception);
        }
    }

    public byte[] exportExpenses(User user, ExpenseQueryParams queryParams, ExpenseExportJobType exportType) {
        return switch (exportType) {
            case CSV -> exportExpensesAsCsv(user, queryParams);
            case PDF -> exportExpensesAsPdf(user, queryParams);
        };
    }

    private String escapeCsv(String value) {
        if (value == null) {
            return "";
        }

        String escapedValue = value.replace("\"", "\"\"");
        return "\"" + escapedValue + "\"";
    }
}
