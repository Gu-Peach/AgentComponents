from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any


class DocumentReader:
    """Read document blobs from local storage keys or direct text payloads."""

    def read(self, document_id: str | None = None, storage_key: str | None = None, upload_id: str | None = None, text: str | None = None) -> dict[str, Any]:
        if text is not None:
            return {"document_id": document_id or "inline", "mime_type": "text/plain", "content": text, "metadata": {"source": "inline"}}
        path_value = storage_key or upload_id
        if not path_value:
            raise ValueError("DocumentReader requires document_id, storage_key, upload_id, or text.")
        path = Path(path_value)
        if not path.exists():
            raise FileNotFoundError(path_value)
        return {"document_id": document_id or path.stem, "mime_type": self._mime_type(path), "content": path.read_bytes(), "metadata": {"source": "file", "path": str(path)}}

    @staticmethod
    def _mime_type(path: Path) -> str:
        suffix = path.suffix.lower()
        return {
            ".md": "text/markdown",
            ".txt": "text/plain",
            ".csv": "text/csv",
            ".json": "application/json",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".pdf": "application/pdf",
        }.get(suffix, "application/octet-stream")


class DocumentParser:
    def parse(self, document_blob: bytes | str, mime_type: str) -> dict[str, Any]:
        if isinstance(document_blob, bytes) and mime_type.startswith("text/"):
            text = document_blob.decode("utf-8-sig")
            return self._parse_text(text, mime_type)
        if isinstance(document_blob, str):
            return self._parse_text(document_blob, mime_type)
        if mime_type == "text/csv":
            return self._parse_csv(document_blob.decode("utf-8-sig"))
        if mime_type == "application/json":
            return self._parse_json(document_blob.decode("utf-8-sig"))
        if mime_type.endswith("wordprocessingml.document"):
            return self._parse_docx(document_blob)
        if mime_type.endswith("spreadsheetml.sheet"):
            return self._parse_xlsx(document_blob)
        if mime_type == "application/pdf":
            return self._parse_pdf(document_blob)
        return {"sections": [], "tables": [], "key_value_candidates": [], "text_spans": [], "raw_text": ""}

    def _parse_text(self, text: str, mime_type: str) -> dict[str, Any]:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        key_values = []
        for line in lines:
            if "=" in line:
                key, value = line.split("=", 1)
                key_values.append({"key": key.strip(), "value": value.strip(), "source": line})
            elif ":" in line or "：" in line:
                separator = ":" if ":" in line else "："
                key, value = line.split(separator, 1)
                key_values.append({"key": key.strip(), "value": value.strip(), "source": line})
        return {
            "mime_type": mime_type,
            "sections": [{"heading": "Document", "text": text}],
            "tables": [],
            "key_value_candidates": key_values,
            "text_spans": [{"start": 0, "end": len(text), "text": text}],
            "raw_text": text,
        }

    def _parse_csv(self, text: str) -> dict[str, Any]:
        rows = list(csv.reader(io.StringIO(text)))
        return {**self._parse_text(text, "text/csv"), "tables": [{"table_id": "csv_0", "rows": rows}]}

    def _parse_json(self, text: str) -> dict[str, Any]:
        payload = json.loads(text)
        return {**self._parse_text(json.dumps(payload, ensure_ascii=False), "application/json"), "json": payload}

    def _parse_docx(self, document_blob: bytes) -> dict[str, Any]:
        try:
            from docx import Document
        except Exception:
            return {"sections": [], "tables": [], "key_value_candidates": [], "text_spans": [], "raw_text": "", "parser_warning": "python-docx is not installed"}
        doc = Document(io.BytesIO(document_blob))
        text = "\n".join(paragraph.text for paragraph in doc.paragraphs)
        parsed = self._parse_text(text, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        parsed["tables"] = [[[cell.text for cell in row.cells] for row in table.rows] for table in doc.tables]
        return parsed

    def _parse_xlsx(self, document_blob: bytes) -> dict[str, Any]:
        try:
            from openpyxl import load_workbook
        except Exception:
            return {"sections": [], "tables": [], "key_value_candidates": [], "text_spans": [], "raw_text": "", "parser_warning": "openpyxl is not installed"}
        workbook = load_workbook(io.BytesIO(document_blob), data_only=True)
        rows = []
        for sheet in workbook.worksheets:
            for row in sheet.iter_rows(values_only=True):
                rows.append([cell for cell in row])
        text = "\n".join(",".join("" if cell is None else str(cell) for cell in row) for row in rows)
        return {**self._parse_text(text, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"), "tables": [{"table_id": "xlsx_0", "rows": rows}]}

    def _parse_pdf(self, document_blob: bytes) -> dict[str, Any]:
        try:
            import pypdf
        except Exception:
            return {"sections": [], "tables": [], "key_value_candidates": [], "text_spans": [], "raw_text": "", "parser_warning": "pypdf is not installed"}
        reader = pypdf.PdfReader(io.BytesIO(document_blob))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        return self._parse_text(text, "application/pdf")


class UnitNormalizer:
    def normalize(self, params: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized = []
        for param in params:
            item = dict(param)
            if item.get("name") == "process_time_s" and str(item.get("unit")).lower() in {"min", "minute", "minutes", "分钟"}:
                item["value"] = float(item["value"]) * 60
                item["unit"] = "s"
            if item.get("name") == "speed_mps" and str(item.get("unit")).lower() in {"m/s", "米/秒", "mps"}:
                item["unit"] = "m/s"
            normalized.append(item)
        return normalized


class DocumentPatchWriter:
    """Create auditable document patch operations without editing structured scene facts."""

    def create_patch(self, document_id: str, base_version: str | int, insert_text: str, source_trace: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        return {
            "document_id": document_id,
            "base_version": base_version,
            "operations": [{"op": "append_text", "path": "/", "text": insert_text}],
            "source_trace": source_trace or [],
            "approval_required": True,
        }
