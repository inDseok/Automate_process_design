# backend/bom_loader.py

from io import BytesIO
from typing import List, Dict
from openpyxl import load_workbook
from uuid import uuid4
import os

# ✅ 기존 BOM 파서에서 함수 import
from backend.BOM_to_Tree import (수량_병합셀_탐색, 수량병합해제_및_사양컬럼_비활성화,사양명_생성)


def extract_specs_from_bom(binary_data: bytes):
    wb = load_workbook(BytesIO(binary_data), data_only=True)

    results = []

    for ws in wb.worksheets:
        sheet_name = ws.title.strip()

        try:
            수량행, 수량_왼쪽열, 수량_오른열, 헤더깊이 = 수량_병합셀_탐색(ws)

            수량_왼쪽열, 수량_오른열, 사양컬럼_활성화 = (
                수량병합해제_및_사양컬럼_비활성화(
                    ws, 수량행, 수량_왼쪽열, 수량_오른열
                )
            )

            사양목록 = 사양명_생성(
                ws,
                sheet_name,
                수량행,
                수량_왼쪽열,
                수량_오른열,
                헤더깊이,
                사양컬럼_활성화
            )

            if 사양목록:
                results.append({
                    "sheet": sheet_name,
                    "specs": [
                        {"col": col, "spec_name": spec_name}
                        for col, spec_name in 사양목록
                    ]
                })

        except Exception as e:
            # ❗ 이 시트는 사양 시트가 아님 → 조용히 스킵
            print(f"[SPEC SKIP] sheet={sheet_name}, reason={e}")
            continue

    if not results:
        raise Exception("사양을 추출할 수 있는 시트를 찾지 못함")

    return {"sheets": results}

    