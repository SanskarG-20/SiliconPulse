"""
PDF parser service using PyMuPDF (fitz) with optional Gemini vision for charts/tables.
Extracts text, tables, and can use Gemini vision for chart/image analysis.
"""
import logging

import fitz  # PyMuPDF

from app.services.gemini_client import gemini_client
from app.settings import settings

logger = logging.getLogger(__name__)


class PDFParser:
    """PDF parser with optional vision-based chart/table extraction."""

    def __init__(self):
        self.vision_enabled = bool(settings.gemini_api_key)

    def extract_text(self, pdf_bytes: bytes) -> str:
        """Extract all text from PDF."""
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            text_parts = []
            for page_num in range(doc.page_count):
                page = doc[page_num]
                text = page.get_text("text")
                if text.strip():
                    text_parts.append(f"--- Page {page_num + 1} ---\n{text}")
            doc.close()
            return "\n\n".join(text_parts)
        except Exception as e:
            logger.error(f"PDF text extraction failed: {e}")
            return ""

    def extract_tables(self, pdf_bytes: bytes) -> list[dict]:
        """Extract tables from PDF using PyMuPDF's table finder."""
        tables = []
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            for page_num in range(doc.page_count):
                page = doc[page_num]
                tabs = page.find_tables()
                for table_idx, table in enumerate(tabs):
                    try:
                        cells = table.extract()
                        if cells:
                            # Convert to markdown-like table for LLM
                            md_rows = [" | ".join(str(c) for c in row) for row in cells]
                            markdown = "\n".join(md_rows)
                            tables.append({
                                "page": page_num + 1,
                                "table_index": table_idx,
                                "markdown": markdown,
                                "bbox": list(table.bbox),
                            })
                    except Exception as e:
                        logger.debug(f"Table extraction failed on page {page_num}: {e}")
            doc.close()
        except Exception as e:
            logger.error(f"Table extraction failed: {e}")
        return tables

    def extract_images(self, pdf_bytes: bytes) -> list[dict]:
        """Extract images from PDF for vision analysis."""
        images = []
        if not self.vision_enabled:
            return []
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            for page_num in range(doc.page_count):
                page = doc[page_num]
                images_list = page.get_images(full=True)
                for img_idx, img in enumerate(images_list):
                    xref = img[0]
                    try:
                        pix = fitz.Pixmap(doc, xref)
                        if pix.n < 5:  # GRAY or RGB
                            img_bytes = pix.tobytes("png")
                        else:  # CMYK
                            pix = fitz.Pixmap(fitz.csRGB, pix)
                            img_bytes = pix.tobytes("png")
                        images.append({
                            "page": page_num + 1,
                            "index": img_idx,
                            "bytes": img_bytes,
                            "width": pix.width,
                            "height": pix.height,
                        })
                    except Exception as e:
                        logger.debug(f"Image extraction failed: {e}")
            doc.close()
        except Exception as e:
            logger.error(f"Image extraction failed: {e}")
        return images

    async def analyze_chart_with_vision(self, image_bytes: bytes, context: str = "") -> str:
        """Use Gemini vision to analyze a chart/image."""
        if not self.vision_enabled:
            return "Vision analysis unavailable (no API key)"
        try:
            from google.genai.types import Part
            prompt = """Analyze this chart/image for financial/supply-chain intelligence.
Context: {context}

Extract:
1. Key metrics, numbers, trends visible
2. Time periods shown
3. Companies/entities mentioned
4. Any guidance, forecasts, or warnings
5. Supply-chain relevant data (capacity, yield, supply, demand)"""
            prompt = prompt.format(context=context)
            resp = await gemini_client.generate_content_with_fallback(
                [
                    prompt.format(context=context),
                    Part.from_bytes(data=image_bytes, mime_type="image/png"),
                ]
            )
            return resp
        except Exception as e:
            logger.warning(f"Vision analysis failed: {e}")
            return f"Vision analysis error: {e}"

    async def extract_all(self, pdf_bytes: bytes, use_vision: bool = False, context: str = "") -> dict:
        """Extract everything from PDF: text, tables, images, and optional vision analysis."""
        result = {
            "text": self.extract_text(pdf_bytes),
            "tables": self.extract_tables(pdf_bytes),
            "images": [],
        }
        if use_vision and self.vision_enabled:
            images = self.extract_images(pdf_bytes)
            for img in images[:5]:  # limit to first 5 images
                analysis = await self.analyze_chart_with_vision(img["bytes"], context)
                result["images"].append({
                    "page": img["page"],
                    "analysis": analysis,
                    "dims": f"{img['width']}x{img['height']}",
                })
        else:
            result["images"] = self.extract_images(pdf_bytes)
        return result


pdf_parser = PDFParser()
