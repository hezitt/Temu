from pathlib import Path
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

WORD_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": WORD_NAMESPACE}


class DocxTableReadError(RuntimeError):
    pass


class DocxTableReader:
    def read(self, file_path: Path) -> list[list[list[str]]]:
        path = file_path.expanduser().resolve()
        if not path.is_file() or path.suffix.lower() != ".docx":
            raise DocxTableReadError(f"Expected an existing .docx file: {path}")
        try:
            with ZipFile(path) as archive:
                xml = archive.read("word/document.xml")
        except (BadZipFile, KeyError, OSError) as exc:
            raise DocxTableReadError(f"Cannot read DOCX tables: {exc}") from exc
        root = ElementTree.fromstring(xml)
        tables: list[list[list[str]]] = []
        for table in root.findall(".//w:tbl", NS):
            rows: list[list[str]] = []
            for row in table.findall("./w:tr", NS):
                cells: list[str] = []
                for cell in row.findall("./w:tc", NS):
                    paragraphs = []
                    for paragraph in cell.findall(".//w:p", NS):
                        text = "".join(
                            node.text or "" for node in paragraph.findall(".//w:t", NS)
                        ).strip()
                        if text:
                            paragraphs.append(text)
                    cells.append(" / ".join(paragraphs))
                rows.append(cells)
            tables.append(rows)
        return tables
