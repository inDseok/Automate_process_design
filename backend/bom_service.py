import os
import json
import tempfile
import subprocess
from uuid import uuid4
from typing import Dict, Any
from pathlib import Path

from backend.bom_loader import extract_specs_from_bom

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data" / "bom_runs"
DATA_DIR.mkdir(parents=True, exist_ok=True)

PYTHON_EXE = r"C:\Users\USER\AppData\Local\Programs\Python\Python39\python.exe"
BOM_TO_TREE_PATH = BASE_DIR / "BOM_to_Tree.py"

SUPPORTED_SUFFIX = {".xlsx", ".xlsm", ".xltx", ".xltm"}

def _ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)


def create_bom_run(binary_data: bytes, original_filename: str) -> Dict[str, Any]:
    """
    BOM 업로드 → BOM_to_Tree 내부 변환(xlsb/xls/xlsm → xlsx)
               → 트리 엑셀 1회 생성
               → 변환된 xlsx 기준으로 사양 추출
    """
    suffix = Path(original_filename).suffix.lower()

    bom_id = str(uuid4())
    root = DATA_DIR / bom_id
    _ensure_dir(root)

    # 1. 업로드 원본 그대로 저장
    bom_path = root / original_filename
    bom_path.write_bytes(binary_data)

    print(f"[BOM] saved original: {bom_path}")

    # 2. 트리 엑셀 생성 (BOM_to_Tree 내부에서 변환 수행)
    tree_excel_path = root / "tree.xlsx"

    print("[RUN] BOM_to_Tree (with internal convert)")

    result = subprocess.run(
        [
            PYTHON_EXE,
            str(BOM_TO_TREE_PATH),
            str(bom_path),
            str(tree_excel_path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    print("=== BOM_to_Tree STDOUT ===")
    print(result.stdout)
    print("=== BOM_to_Tree STDERR ===")
    print(result.stderr)

    if result.returncode != 0:
        raise RuntimeError("BOM_to_Tree 실행 실패")

    if not tree_excel_path.exists():
        raise RuntimeError("tree.xlsx가 생성되지 않음")

    # 3. BOM_to_Tree가 생성한 변환 xlsx 찾기
    # (보통 _converted.xlsx 규칙)
    converted_candidates = list(root.glob("*_converted.xlsx"))
    if not converted_candidates:
        raise RuntimeError("변환된 xlsx 파일을 찾을 수 없음")

    converted_xlsx = converted_candidates[0]
    print(f"[BOM] using converted xlsx: {converted_xlsx}")

    # 4. 변환된 xlsx 기준으로 사양 추출
    with open(converted_xlsx, "rb") as f:
        spec_info = extract_specs_from_bom(f.read())

    if not spec_info.get("sheets"):
        raise RuntimeError("사양 추출 결과가 비어 있음")

    # 5. meta.json
    meta = {
        "bom_id": bom_id,
        "original_filename": original_filename,
        "converted_xlsx": converted_xlsx.name,
        "tree_excel": "tree.xlsx",
        "spec_info": spec_info,
    }

    (root / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"[DONE] BOM RUN completed: {bom_id}")

    return meta



