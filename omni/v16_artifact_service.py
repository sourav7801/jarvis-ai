"""Verified office/artifact generation for JARVIS V16.

Artifacts are generated into managed runtime storage, reopened with the native
Python reader for their format, and only then reported as verified.  Generated
files can also be registered with the V16 file service so Chat/Files/Projects
share one stable file_id.

This is the V16 foundation, not a replacement for specialized Office agents.
Those agents should submit structured artifact specifications to this service.
"""

from __future__ import annotations

from datetime import datetime, timezone
import csv
import json
import os
from pathlib import Path
import re
from threading import RLock
from typing import Any, Mapping, Sequence
import uuid


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = PROJECT_ROOT / "data" / "workspaces" / "artifacts"
_SAFE_WORKSPACE = re.compile(r"^[A-Z0-9][A-Z0-9_-]{0,63}$")
_SUPPORTED = {"xlsx", "csv", "docx", "pptx", "pdf", "md", "json", "txt"}


class ArtifactServiceV16:
    def __init__(self, root: Path | str = DEFAULT_ROOT) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()

    @staticmethod
    def _workspace(value: str | None) -> str:
        token = str(value or "HOME").strip().upper().replace(" ", "_")
        if not _SAFE_WORKSPACE.fullmatch(token):
            raise ValueError("invalid workspace")
        return token

    @staticmethod
    def _filename(filename: str, kind: str) -> str:
        raw = str(filename or "").strip()
        if not raw or raw != Path(raw).name or "/" in raw or "\\" in raw:
            raise ValueError("artifact filename must be a filename, not a path")
        cleaned = re.sub(r"[^A-Za-z0-9._()\- ]+", "_", raw).strip(" .")
        expected = "." + kind
        if Path(cleaned).suffix.lower() != expected:
            cleaned = (Path(cleaned).stem or "artifact") + expected
        return cleaned[:180]

    def _target(self, workspace: str, filename: str) -> Path:
        directory = (self.root / workspace).resolve()
        if self.root not in directory.parents and directory != self.root:
            raise RuntimeError("artifact workspace escaped managed root")
        directory.mkdir(parents=True, exist_ok=True)
        target = (directory / filename).resolve()
        if target.parent != directory:
            raise RuntimeError("artifact target escaped workspace")
        return target

    @staticmethod
    def _atomic_replace(temporary: Path, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(temporary, target)

    def create(
        self,
        kind: str,
        filename: str,
        specification: Mapping[str, Any] | Sequence[Any] | str,
        *,
        workspace: str = "HOME",
        register_file: bool = True,
    ) -> dict[str, Any]:
        artifact_kind = str(kind or "").lower().lstrip(".")
        if artifact_kind not in _SUPPORTED:
            raise ValueError(f"unsupported artifact type: {artifact_kind}")
        workspace_name = self._workspace(workspace)
        safe_name = self._filename(filename, artifact_kind)
        target = self._target(workspace_name, safe_name)
        temporary = target.with_name(f".{target.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
        with self._lock:
            if artifact_kind == "xlsx":
                self._create_xlsx(temporary, specification)
            elif artifact_kind == "csv":
                self._create_csv(temporary, specification)
            elif artifact_kind == "docx":
                self._create_docx(temporary, specification)
            elif artifact_kind == "pptx":
                self._create_pptx(temporary, specification)
            elif artifact_kind == "pdf":
                self._create_pdf(temporary, specification)
            elif artifact_kind == "json":
                self._create_json(temporary, specification)
            else:
                self._create_text(temporary, specification)
            self._atomic_replace(temporary, target)
            verification = self.verify(target, artifact_kind)
            if not verification.get("verified"):
                raise RuntimeError(f"artifact verification failed: {verification.get('reason')}")

        file_registration = None
        if register_file:
            try:
                from omni.v16_file_service import MANAGED_FILE_SERVICE_V16

                file_registration = MANAGED_FILE_SERVICE_V16.register_path(
                    target, original_name=safe_name, workspace=workspace_name
                )
            except Exception as exc:
                # The artifact remains valid even if indexing is temporarily
                # degraded; surface the failure explicitly instead of hiding it.
                file_registration = {
                    "success": False,
                    "reason": f"{type(exc).__name__}: {exc}"[:500],
                }

        return {
            "success": True,
            "version": "16.0",
            "service": "JARVIS_V16_VERIFIED_ARTIFACT_SERVICE",
            "kind": artifact_kind,
            "filename": safe_name,
            "workspace": workspace_name,
            "path": str(target),
            "size_bytes": target.stat().st_size,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "verification": verification,
            "file_registration": file_registration,
        }

    @staticmethod
    def _sheet_rows(sheet: Mapping[str, Any]) -> list[list[Any]]:
        rows = sheet.get("rows") or []
        if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes, bytearray)):
            raise ValueError("spreadsheet sheet.rows must be a sequence")
        normalized: list[list[Any]] = []
        for row in rows:
            if isinstance(row, Mapping):
                normalized.append(list(row.values()))
            elif isinstance(row, Sequence) and not isinstance(row, (str, bytes, bytearray)):
                normalized.append(list(row))
            else:
                normalized.append([row])
        return normalized

    @classmethod
    def _create_xlsx(cls, path: Path, spec: Any) -> None:
        from openpyxl import Workbook
        from openpyxl.chart import BarChart, LineChart, Reference
        from openpyxl.styles import Alignment, Font
        from openpyxl.utils import get_column_letter

        payload = dict(spec) if isinstance(spec, Mapping) else {"sheets": [{"name": "Sheet1", "rows": spec}]}
        sheets = payload.get("sheets") or [{"name": "Sheet1", "rows": []}]
        if not isinstance(sheets, Sequence):
            raise ValueError("xlsx specification requires a sheets sequence")
        workbook = Workbook()
        default = workbook.active
        workbook.remove(default)

        for index, raw_sheet in enumerate(sheets, start=1):
            sheet = dict(raw_sheet or {}) if isinstance(raw_sheet, Mapping) else {"rows": raw_sheet}
            title = re.sub(r"[\\/*?:\[\]]+", "_", str(sheet.get("name") or f"Sheet{index}"))[:31] or f"Sheet{index}"
            worksheet = workbook.create_sheet(title=title)
            rows = cls._sheet_rows(sheet)
            for row in rows:
                worksheet.append(row)

            header_row = int(sheet.get("header_row") or (1 if rows else 0))
            if header_row and header_row <= worksheet.max_row:
                for cell in worksheet[header_row]:
                    cell.font = Font(bold=True)
                    cell.alignment = Alignment(vertical="center")

            freeze = sheet.get("freeze_panes")
            if freeze:
                worksheet.freeze_panes = str(freeze)
            if sheet.get("auto_filter") and worksheet.max_row and worksheet.max_column:
                worksheet.auto_filter.ref = worksheet.dimensions

            widths = sheet.get("column_widths") or {}
            if isinstance(widths, Mapping):
                for column, width in widths.items():
                    worksheet.column_dimensions[str(column).upper()].width = float(width)
            elif sheet.get("auto_width", True):
                for column_index in range(1, worksheet.max_column + 1):
                    longest = 0
                    for row_index in range(1, min(worksheet.max_row, 1000) + 1):
                        value = worksheet.cell(row_index, column_index).value
                        longest = max(longest, len(str(value)) if value is not None else 0)
                    worksheet.column_dimensions[get_column_letter(column_index)].width = min(max(longest + 2, 9), 45)

            for chart_spec in list(sheet.get("charts") or []):
                if not isinstance(chart_spec, Mapping):
                    continue
                chart_type = str(chart_spec.get("type") or "line").lower()
                chart = BarChart() if chart_type == "bar" else LineChart()
                chart.title = str(chart_spec.get("title") or "")
                min_col = int(chart_spec.get("min_col") or 2)
                max_col = int(chart_spec.get("max_col") or worksheet.max_column)
                min_row = int(chart_spec.get("min_row") or 1)
                max_row = int(chart_spec.get("max_row") or worksheet.max_row)
                if max_col >= min_col and max_row >= min_row:
                    data = Reference(worksheet, min_col=min_col, max_col=max_col, min_row=min_row, max_row=max_row)
                    chart.add_data(data, titles_from_data=bool(chart_spec.get("titles_from_data", True)))
                    category_col = int(chart_spec.get("category_col") or 1)
                    categories = Reference(worksheet, min_col=category_col, min_row=min_row + (1 if chart_spec.get("titles_from_data", True) else 0), max_row=max_row)
                    chart.set_categories(categories)
                    worksheet.add_chart(chart, str(chart_spec.get("anchor") or "H2"))

        if not workbook.sheetnames:
            workbook.create_sheet("Sheet1")
        workbook.save(path)
        workbook.close()

    @staticmethod
    def _rows_from_spec(spec: Any) -> list[list[Any]]:
        if isinstance(spec, Mapping):
            rows = spec.get("rows") or []
        else:
            rows = spec
        if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes, bytearray)):
            raise ValueError("rows must be a sequence")
        result = []
        for row in rows:
            if isinstance(row, Mapping):
                result.append(list(row.values()))
            elif isinstance(row, Sequence) and not isinstance(row, (str, bytes, bytearray)):
                result.append(list(row))
            else:
                result.append([row])
        return result

    @classmethod
    def _create_csv(cls, path: Path, spec: Any) -> None:
        rows = cls._rows_from_spec(spec)
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerows(rows)

    @staticmethod
    def _create_docx(path: Path, spec: Any) -> None:
        from docx import Document

        payload = dict(spec) if isinstance(spec, Mapping) else {"paragraphs": [str(spec)]}
        document = Document()
        title = payload.get("title")
        if title:
            document.add_heading(str(title), 0)
        for block in list(payload.get("blocks") or []):
            if not isinstance(block, Mapping):
                document.add_paragraph(str(block))
                continue
            kind = str(block.get("type") or "paragraph").lower()
            if kind == "heading":
                document.add_heading(str(block.get("text") or ""), level=max(1, min(int(block.get("level") or 1), 9)))
            elif kind == "table":
                rows = block.get("rows") or []
                normalized = [list(row) for row in rows if isinstance(row, Sequence) and not isinstance(row, (str, bytes))]
                if normalized:
                    columns = max(len(row) for row in normalized)
                    table = document.add_table(rows=len(normalized), cols=columns)
                    for r, values in enumerate(normalized):
                        for c, value in enumerate(values):
                            table.cell(r, c).text = "" if value is None else str(value)
            elif kind == "bullet":
                document.add_paragraph(str(block.get("text") or ""), style="List Bullet")
            else:
                document.add_paragraph(str(block.get("text") or ""))
        for paragraph in list(payload.get("paragraphs") or []):
            document.add_paragraph(str(paragraph))
        document.save(path)

    @staticmethod
    def _create_pptx(path: Path, spec: Any) -> None:
        from pptx import Presentation

        payload = dict(spec) if isinstance(spec, Mapping) else {"slides": [{"title": "JARVIS", "body": str(spec)}]}
        presentation = Presentation()
        # Remove the implicit first slide only if a template created one.
        for slide_spec in list(payload.get("slides") or []):
            row = dict(slide_spec or {}) if isinstance(slide_spec, Mapping) else {"body": str(slide_spec)}
            layout_index = 1 if len(presentation.slide_layouts) > 1 else 0
            slide = presentation.slides.add_slide(presentation.slide_layouts[layout_index])
            if slide.shapes.title is not None:
                slide.shapes.title.text = str(row.get("title") or "")
            body = row.get("bullets") if row.get("bullets") is not None else row.get("body")
            placeholders = [shape for shape in slide.placeholders if shape != slide.shapes.title]
            if placeholders:
                frame = placeholders[0].text_frame
                frame.clear()
                values = body if isinstance(body, Sequence) and not isinstance(body, str) else [body or ""]
                for idx, value in enumerate(values):
                    paragraph = frame.paragraphs[0] if idx == 0 else frame.add_paragraph()
                    paragraph.text = str(value)
        presentation.save(path)

    @staticmethod
    def _create_pdf(path: Path, spec: Any) -> None:
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas
        except ImportError as exc:
            raise RuntimeError("reportlab is required for PDF generation") from exc
        payload = dict(spec) if isinstance(spec, Mapping) else {"paragraphs": [str(spec)]}
        lines = []
        if payload.get("title"):
            lines.append(str(payload["title"]))
            lines.append("")
        lines.extend(str(item) for item in list(payload.get("paragraphs") or []))
        pdf = canvas.Canvas(str(path), pagesize=A4)
        width, height = A4
        y = height - 50
        for logical_line in lines or [""]:
            chunks = [logical_line[i : i + 100] for i in range(0, max(len(logical_line), 1), 100)] or [""]
            for line in chunks:
                if y < 50:
                    pdf.showPage()
                    y = height - 50
                pdf.drawString(50, y, line)
                y -= 16
        pdf.save()

    @staticmethod
    def _create_json(path: Path, spec: Any) -> None:
        path.write_text(json.dumps(spec, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    @staticmethod
    def _create_text(path: Path, spec: Any) -> None:
        if isinstance(spec, str):
            text = spec
        elif isinstance(spec, Mapping) and "text" in spec:
            text = str(spec.get("text") or "")
        else:
            text = json.dumps(spec, ensure_ascii=False, indent=2, default=str)
        path.write_text(text, encoding="utf-8")

    @staticmethod
    def verify(path: Path | str, kind: str | None = None) -> dict[str, Any]:
        target = Path(path)
        artifact_kind = str(kind or target.suffix.lstrip(".")).lower()
        if not target.is_file() or target.stat().st_size <= 0:
            return {"verified": False, "reason": "FILE_MISSING_OR_EMPTY"}
        try:
            if artifact_kind == "xlsx":
                from openpyxl import load_workbook
                workbook = load_workbook(target, read_only=True, data_only=False)
                try:
                    detail = {"sheets": list(workbook.sheetnames), "sheet_count": len(workbook.sheetnames)}
                finally:
                    workbook.close()
            elif artifact_kind == "docx":
                from docx import Document
                document = Document(target)
                detail = {"paragraphs": len(document.paragraphs), "tables": len(document.tables)}
            elif artifact_kind == "pptx":
                from pptx import Presentation
                presentation = Presentation(target)
                detail = {"slides": len(presentation.slides)}
            elif artifact_kind == "pdf":
                try:
                    from pypdf import PdfReader
                except ImportError:
                    from PyPDF2 import PdfReader
                reader = PdfReader(str(target))
                detail = {"pages": len(reader.pages)}
            elif artifact_kind == "json":
                json.loads(target.read_text(encoding="utf-8"))
                detail = {"json": True}
            elif artifact_kind == "csv":
                with target.open("r", encoding="utf-8-sig", errors="strict", newline="") as handle:
                    rows = sum(1 for _ in csv.reader(handle))
                detail = {"rows": rows}
            else:
                target.read_text(encoding="utf-8", errors="strict")
                detail = {"text": True}
        except Exception as exc:
            return {"verified": False, "reason": f"{type(exc).__name__}: {exc}"[:500]}
        return {"verified": True, "kind": artifact_kind, **detail}

    def status(self) -> dict[str, Any]:
        return {
            "success": True,
            "version": "16.0",
            "service": "JARVIS_V16_VERIFIED_ARTIFACT_SERVICE",
            "supported": sorted(_SUPPORTED),
            "reopen_and_verify": True,
            "file_service_registration": True,
            "live_external_action": False,
        }


ARTIFACT_SERVICE_V16 = ArtifactServiceV16()


__all__ = ["ArtifactServiceV16", "ARTIFACT_SERVICE_V16"]
