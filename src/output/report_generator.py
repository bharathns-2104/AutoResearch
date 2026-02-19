from datetime import datetime
from pathlib import Path

from src.orchestration.logger import setup_logger
from src.output.data_mapper import ReportDataMapper
from src.output.report_validator import ReportValidator
from src.output.pdf_generator import PDFGenerator
from src.output.ppt_generator import PPTGenerator

logger = setup_logger()


class ReportGenerator:

    def __init__(self, output_dir="reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ======================================================
    # MAIN ENTRY POINT
    # ======================================================

    def generate(self, consolidated_data, generate_ppt=True):
        """
        Generates PDF and optionally PPT report
        from consolidated JSON output.
        """

        logger.info("Starting report generation process")

        # ------------------------------------------
        # STEP 1 – VALIDATE INPUT JSON
        # ------------------------------------------
        try:
            validator = ReportValidator()
            validator.validate(consolidated_data)
            logger.info("Consolidated data validation successful")
        except Exception as e:
            logger.error(f"Validation failed: {str(e)}")
            raise

        # ------------------------------------------
        # STEP 2 – MAP DATA TO REPORT SECTIONS
        # ------------------------------------------
        try:
            mapper = ReportDataMapper()
            mapped_data = mapper.map(consolidated_data)
            logger.info("Data mapping successful")
        except Exception as e:
            logger.error(f"Data mapping failed: {str(e)}")
            raise

        # ------------------------------------------
        # STEP 3 – PREPARE FILE PATHS
        # ------------------------------------------
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        pdf_path = self.output_dir / f"final_report_{timestamp}.pdf"
        ppt_path = self.output_dir / f"final_report_{timestamp}.pptx"

        generated_paths = {
            "pdf": None,
            "ppt": None
        }

        # ------------------------------------------
        # STEP 4 – GENERATE PDF (SAFE MODE)
        # ------------------------------------------
        try:
            logger.info("Generating PDF report")
            pdf_generator = PDFGenerator()
            pdf_generator.generate(mapped_data, pdf_path)
            generated_paths["pdf"] = str(pdf_path)
            logger.info(f"PDF generated successfully: {pdf_path}")
        except Exception as e:
            logger.error(f"PDF generation failed: {str(e)}")
            generated_paths["pdf"] = None

        # ------------------------------------------
        # STEP 5 – GENERATE PPT (OPTIONAL + SAFE)
        # ------------------------------------------
        if generate_ppt:
            try:
                logger.info("Generating PPT report")
                ppt_generator = PPTGenerator()
                ppt_generator.generate(mapped_data, ppt_path)
                generated_paths["ppt"] = str(ppt_path)
                logger.info(f"PPT generated successfully: {ppt_path}")
            except Exception as e:
                logger.error(f"PPT generation failed: {str(e)}")
                generated_paths["ppt"] = None

        # ------------------------------------------
        # STEP 6 – FINAL VALIDATION OF OUTPUT
        # ------------------------------------------
        if not generated_paths["pdf"] and not generated_paths["ppt"]:
            logger.error("Both PDF and PPT generation failed")
            raise RuntimeError("Report generation failed completely")

        logger.info("Report generation process completed")

        return generated_paths
