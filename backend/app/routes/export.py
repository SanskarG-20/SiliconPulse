from fastapi import APIRouter, Depends, Response, HTTPException
from datetime import datetime
import json

from ..models import ExportRequest, EvidenceItem
from ..core.auth import get_current_user

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.post("/export")
async def export_analysis(request: ExportRequest):
    """Export the analysis report in the requested format."""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"siliconpulse_report_{timestamp}"
        content = ""
        media_type = "text/plain"

        if request.format == "md":
            filename += ".md"
            media_type = "text/markdown"
            content = f"# SiliconPulse Intelligence Report\n\n"
            content += f"**Query:** {request.query}\n"
            content += f"**Date:** {datetime.now().isoformat()}\n\n"
            content += f"## Strategic Insight\n\n{request.report}\n\n"

            if request.include_evidence:
                content += f"## Evidence\n\n"
                for item in request.evidence:
                    content += f"- **{item.title}** ({item.source})\n"
                    content += f"  - {item.snippet}\n"
                    if item.url:
                        content += f"  - [Link]({item.url})\n"
                    content += "\n"

        elif request.format == "json":
            filename += ".json"
            media_type = "application/json"
            export_data = {
                "query": request.query,
                "timestamp": datetime.now().isoformat(),
                "report": request.report
            }
            if request.include_evidence:
                export_data["evidence"] = [item.dict() for item in request.evidence]
            content = json.dumps(export_data, indent=2)

        elif request.format == "txt":
            filename += ".txt"
            media_type = "text/plain"
            content = f"SILICONPULSE INTELLIGENCE REPORT\n"
            content += f"==============================\n"
            content += f"Query: {request.query}\n"
            content += f"Date: {datetime.now().isoformat()}\n\n"
            content += f"STRATEGIC INSIGHT\n"
            content += f"-----------------\n"
            content += f"{request.report}\n\n"

            if request.include_evidence:
                content += f"EVIDENCE\n"
                content += f"--------\n"
                for item in request.evidence:
                    content += f"* {item.title} ({item.source})\n"
                    content += f"  {item.snippet}\n"
                    if item.url:
                        content += f"  Link: {item.url}\n"
                    content += "\n"

        elif request.format == "pdf":
            filename += ".txt"
            content = "PDF export not configured. Returning text format.\n\n" + request.report

        return Response(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Export failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))