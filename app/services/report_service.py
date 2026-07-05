"""
DataInsight API — Report Service
================================
Consolidates insights across all modules and generates a professional PDF
using ReportLab.
"""

from __future__ import annotations

import datetime
import pathlib
import time
import uuid

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.schemas.correlation import CorrelationRequest
from app.schemas.outliers import OutlierDetectionRequest, OutlierMethod
from app.schemas.report import ReportGenerationRequest, ReportGenerationResponse
from app.schemas.visualization import (
    HistogramRequest,
    ScatterPlotRequest,
    VisualizationBatchRequest,
)
from app.schemas.analysis import AnalysisRequest
from app.services.stats_service import StatisticalAnalysisEngine
from app.services.correlation_service import CorrelationService
from app.services.dataset_service import DatasetService
from app.services.missing_values_service import MissingValuesService
from app.services.outlier_service import OutlierDetectionService
from app.services.visualization_service import VisualizationService
from app.utils.logger import get_logger

logger = get_logger(__name__)


# ===========================================================================
# ReportLab Styling & Templates
# ===========================================================================

class ReportStyling:
    """Contains standard corporate styles for the PDF."""

    # Colors
    PRIMARY = colors.HexColor("#4f46e5")  # indigo-600
    DARK    = colors.HexColor("#1e293b")  # slate-800
    MUTED   = colors.HexColor("#64748b")  # slate-500
    LIGHT   = colors.HexColor("#f8fafc")  # slate-50
    BORDER  = colors.HexColor("#cbd5e1")  # slate-300

    def __init__(self):
        self.styles = getSampleStyleSheet()
        
        self.title = ParagraphStyle(
            'ReportTitle',
            parent=self.styles['Heading1'],
            fontSize=28,
            textColor=self.PRIMARY,
            spaceAfter=30,
            alignment=1, # center
            fontName="Helvetica-Bold",
        )
        self.heading1 = ParagraphStyle(
            'Heading1',
            parent=self.styles['Heading2'],
            fontSize=18,
            textColor=self.DARK,
            spaceBefore=20,
            spaceAfter=15,
            fontName="Helvetica-Bold",
        )
        self.heading2 = ParagraphStyle(
            'Heading2',
            parent=self.styles['Heading3'],
            fontSize=14,
            textColor=self.PRIMARY,
            spaceBefore=15,
            spaceAfter=10,
            fontName="Helvetica-Bold",
        )
        self.normal = ParagraphStyle(
            'Normal',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=self.DARK,
            spaceAfter=10,
            leading=14,
        )
        self.bullet = ParagraphStyle(
            'Bullet',
            parent=self.normal,
            leftIndent=20,
            bulletIndent=10,
            spaceAfter=5,
        )

    def get_table_style(self) -> TableStyle:
        return TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), self.PRIMARY),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), self.LIGHT),
            ('TEXTCOLOR', (0, 1), (-1, -1), self.DARK),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, self.BORDER),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, self.LIGHT]),
        ])


def _header_footer(canvas, doc, title: str):
    canvas.saveState()
    
    # Header
    canvas.setFont('Helvetica-Bold', 10)
    canvas.setFillColor(ReportStyling.MUTED)
    canvas.drawString(inch, A4[1] - 0.5 * inch, "DataInsight API")
    canvas.drawRightString(A4[0] - inch, A4[1] - 0.5 * inch, title)
    
    # Footer
    page_num = canvas.getPageNumber()
    canvas.setFont('Helvetica', 9)
    canvas.drawString(inch, 0.5 * inch, f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    canvas.drawRightString(A4[0] - inch, 0.5 * inch, f"Page {page_num}")
    
    canvas.restoreState()


# ===========================================================================
# Recommendations Engine
# ===========================================================================

class RuleBasedRecommender:
    """Generates rule-based recommendations based on analyzed metrics."""
    
    @staticmethod
    def generate(missing_report, outlier_report, corr_report) -> list[str]:
        recs = []
        
        # Missing values rules
        for col in missing_report.columns:
            if col.missing_pct > 30:
                recs.append(f"<b>{col.column}</b> has a critically high missing value rate ({col.missing_pct}%). Consider dropping this feature or imputing with advanced techniques.")
            elif col.missing_pct > 5:
                recs.append(f"<b>{col.column}</b> has {col.missing_pct}% missing values. Consider imputing with the median or using iterative imputation.")
                
        # Outlier rules
        if outlier_report:
            outlier_pct = round((outlier_report.total_outlier_rows / (outlier_report.total_outlier_rows + 1)) * 100, 1) # Approximation since we don't pass total_rows here, we will just use raw count
            if outlier_report.total_outlier_rows > 0:
                recs.append(f"Detected <b>{outlier_report.total_outlier_rows}</b> rows with outliers across {len(outlier_report.affected_columns)} columns. Review the boxplots and consider applying clipping (Winsorization) or removing these rows before training predictive models.")

        # Correlation rules
        for pair in corr_report.highly_correlated_pairs:
            recs.append(f"<b>{pair.feature_x}</b> and <b>{pair.feature_y}</b> are highly correlated ({pair.correlation}). To prevent multicollinearity, consider removing one of them or applying PCA.")

        if not recs:
            recs.append("The dataset appears generally clean and well-formed. Standard modeling pipelines can proceed.")
            
        return recs


# ===========================================================================
# Report Service Orchestrator
# ===========================================================================

class ReportService:
    def __init__(
        self,
        dataset_service: DatasetService,
        analysis_service: StatisticalAnalysisEngine,
        missing_values_service: MissingValuesService,
        outlier_service: OutlierDetectionService,
        correlation_service: CorrelationService,
        visualization_service: VisualizationService,
        reports_dir: pathlib.Path,
    ):
        self.dataset = dataset_service
        self.analysis = analysis_service
        self.missing = missing_values_service
        self.outliers = outlier_service
        self.correlation = correlation_service
        self.viz = visualization_service
        self.reports_dir = reports_dir
        self.style = ReportStyling()

    def generate_report(self, dataset_id: str, request: ReportGenerationRequest, api_base_url: str) -> ReportGenerationResponse:
        t_start = time.perf_counter()
        
        # 1. Fetch Metadata
        meta = self.dataset.get_dataset(dataset_id)
        if not meta:
            raise ValueError(f"Dataset {dataset_id} not found")
        
        df = self.dataset.load_dataframe(dataset_id)
        numeric_cols = df.select_dtypes(include='number').columns.tolist()

        title = request.title or f"Data Analytics Report: {meta.original_filename}"
        report_id = str(uuid.uuid4())
        filename = f"report_{report_id}.pdf"
        
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = self.reports_dir / filename

        # 2. Run Analytics (Orchestration)
        logger.info("Report generation started, orchestrating analysis...", dataset_id=dataset_id)
        
        try:
            stat_rep    = self.analysis.analyse(dataset_id, AnalysisRequest())
            miss_rep    = self.missing.analyse(dataset_id, api_base_url)
            out_rep     = self.outliers.detect(dataset_id, OutlierDetectionRequest(method=OutlierMethod.IQR, generate_boxplots=True), api_base_url)
            corr_rep    = self.correlation.analyse(dataset_id, CorrelationRequest(generate_charts=True), api_base_url)
            
            # Request some basic visuals if applicable
            viz_rep = None
            if request.include_visualizations and numeric_cols:
                charts = []
                # Add a histogram for the first numeric column
                charts.append(HistogramRequest(column=numeric_cols[0]))
                # Add a scatter if we have at least 2 numeric columns
                if len(numeric_cols) >= 2:
                    charts.append(ScatterPlotRequest(x=numeric_cols[0], y=numeric_cols[1]))
                
                if charts:
                    viz_rep = self.viz.generate_batch(
                        dataset_id, 
                        VisualizationBatchRequest(charts=charts), 
                        api_base_url
                    )

        except Exception as exc:
            logger.error(f"Failed to gather insights for report: {exc}")
            raise RuntimeError(f"Report generation failed during analysis phase: {exc}")

        # 3. Build PDF Elements
        elements = []
        
        # --- TITLE ---
        elements.append(Spacer(1, 2 * inch))
        elements.append(Paragraph(title, self.style.title))
        elements.append(Paragraph(f"Prepared by: {request.author}", ParagraphStyle('sub', parent=self.style.normal, alignment=1)))
        elements.append(Paragraph(f"Date: {datetime.date.today().isoformat()}", ParagraphStyle('sub', parent=self.style.normal, alignment=1)))
        elements.append(PageBreak())

        # --- DATASET SUMMARY ---
        elements.append(Paragraph("1. Dataset Summary", self.style.heading1))
        
        summary_data = [
            ["Metric", "Value"],
            ["Filename", meta.original_filename],
            ["Rows", str(meta.row_count)],
            ["Columns", str(meta.column_count)],
            ["Upload Time", str(meta.uploaded_at)],
        ]
        elements.append(Table(summary_data, style=self.style.get_table_style(), colWidths=[2*inch, 4*inch]))
        elements.append(Spacer(1, 0.3*inch))

        # --- MISSING VALUES ---
        elements.append(Paragraph("2. Missing Values Analysis", self.style.heading1))
        
        miss_data = [["Column", "Missing Count", "Missing Percentage"]]
        for col in miss_rep.columns:
            if col.missing_count > 0:
                miss_data.append([col.column, str(col.missing_count), f"{col.missing_pct}%"])
        
        if len(miss_data) > 1:
            elements.append(Table(miss_data, style=self.style.get_table_style(), colWidths=[3*inch, 1.5*inch, 1.5*inch]))
        else:
            elements.append(Paragraph("No missing values detected in the dataset.", self.style.normal))

        if miss_rep.chart and miss_rep.chart.chart_path:
            elements.append(Spacer(1, 0.2*inch))
            try:
                img = Image(miss_rep.chart.chart_path, width=6*inch, height=3*inch)
                elements.append(KeepTogether([img]))
            except Exception:
                pass
                
        elements.append(PageBreak())

        # --- STATISTICS ---
        elements.append(Paragraph("3. Statistical Summary", self.style.heading1))
        stat_data = [["Column", "Mean", "Median", "Min", "Max", "Std Dev"]]
        for name, stats in stat_rep.columns.items():
            stat_data.append([
                name,
                f"{stats.mean:.2f}" if stats.mean is not None else "-",
                f"{stats.median:.2f}" if stats.median is not None else "-",
                f"{stats.minimum:.2f}" if stats.minimum is not None else "-",
                f"{stats.maximum:.2f}" if stats.maximum is not None else "-",
                f"{stats.std_dev:.2f}" if stats.std_dev is not None else "-",
            ])
        elements.append(Table(stat_data, style=self.style.get_table_style(), colWidths=[1.5*inch, 1*inch, 1*inch, 1*inch, 1*inch, 1*inch]))
        
        # --- OUTLIERS ---
        elements.append(Paragraph("4. Outlier Detection (IQR)", self.style.heading1))
        elements.append(Paragraph(f"Detected outliers in {out_rep.total_outlier_rows} distinct rows.", self.style.normal))
        
        if out_rep.chart and out_rep.chart.chart_path:
            try:
                img = Image(out_rep.chart.chart_path, width=6.5*inch, height=3*inch)
                elements.append(KeepTogether([img]))
            except Exception:
                pass

        elements.append(PageBreak())

        # --- CORRELATION ---
        elements.append(Paragraph("5. Correlation Analysis", self.style.heading1))
        corr_data = [["Feature X", "Feature Y", "Correlation", "Strength"]]
        for pair in corr_rep.highly_correlated_pairs[:10]: # limit to top 10 for table
            corr_data.append([pair.feature_x, pair.feature_y, str(pair.correlation), pair.strength])
            
        if len(corr_data) > 1:
            elements.append(Table(corr_data, style=self.style.get_table_style(), colWidths=[1.5*inch, 1.5*inch, 1*inch, 2*inch]))
        else:
            elements.append(Paragraph("No highly correlated pairs found.", self.style.normal))

        if corr_rep.chart and corr_rep.chart.png_path:
            elements.append(Spacer(1, 0.2*inch))
            try:
                img = Image(corr_rep.chart.png_path, width=6*inch, height=6*inch)
                elements.append(KeepTogether([img]))
            except Exception:
                pass

        # --- VISUALIZATIONS ---
        if viz_rep and viz_rep.successful_charts > 0:
            elements.append(PageBreak())
            elements.append(Paragraph("6. Additional Visualizations", self.style.heading1))
            for chart in viz_rep.charts:
                if chart.png_url:
                    # Resolve absolute path from URL pattern
                    # e.g., /api/v1/visualizations/chart/viz_xxx.png
                    img_filename = chart.png_url.split("/")[-1]
                    path = str(self.viz._plots_dir / img_filename)
                    try:
                        img = Image(path, width=6*inch, height=4*inch)
                        elements.append(KeepTogether([Spacer(1, 0.1*inch), img]))
                    except Exception as e:
                        logger.warning(f"Could not load viz image for report: {e}")

        # --- RECOMMENDATIONS ---
        elements.append(PageBreak())
        elements.append(Paragraph("Recommendations", self.style.heading1))
        
        if request.include_recommendations:
            recs = RuleBasedRecommender.generate(miss_rep, out_rep, corr_rep)
            for rec in recs:
                elements.append(Paragraph(f"<bullet>•</bullet>{rec}", self.style.bullet))
        else:
            elements.append(Paragraph("Recommendations generation disabled.", self.style.normal))

        # 4. Generate Document
        doc = SimpleDocTemplate(
            str(pdf_path),
            pagesize=A4,
            rightMargin=inch,
            leftMargin=inch,
            topMargin=inch,
            bottomMargin=inch
        )
        
        # Build using the callback for header/footers
        doc.build(
            elements,
            onFirstPage=lambda c, d: _header_footer(c, d, title),
            onLaterPages=lambda c, d: _header_footer(c, d, title)
        )
        
        elapsed = round((time.perf_counter() - t_start) * 1000, 2)
        size_kb = round(pdf_path.stat().st_size / 1024.0, 2)
        
        logger.info("PDF Report generated", dataset_id=dataset_id, file=filename, size_kb=size_kb, elapsed_ms=elapsed)
        
        # Rough page count estimate since reportlab hides the actual final count in SimpleDocTemplate easily
        # A true page count requires custom Canvas or a two-pass build, but for API responses we'll 
        # approximate or return 0 if unavailable.
        return ReportGenerationResponse(
            dataset_id=dataset_id,
            report_id=report_id,
            filename=filename,
            download_url=f"{api_base_url}/reports/download/{filename}",
            file_size_kb=size_kb,
            pages=0, 
            elapsed_ms=elapsed
        )
