from __future__ import annotations

from backend.session_excel import get_or_create_sid, ExcelStore,SessionState, ExcelUploadResponse, ExcelInfo
from typing import Dict, List, Optional, Any

import json
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, Response, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from pydantic import BaseModel
from pathlib import Path

from backend.models import SubTree, SubNodePatch
from backend.excel_loader import list_sub_names, load_sub_tree, parse_uploaded_excel
from fastapi import Cookie
from typing import Optional


app = FastAPI()

templates = Jinja2Templates(directory="frontend/template")
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def load_session_state():
    if not SESSION_STORE_PATH.exists():
        return {}
    try:
        return json.loads(SESSION_STORE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}

def save_session_state():
    SESSION_STORE_PATH.write_text(
        json.dumps(SESSION_STATE, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

DATA_DIR = Path("backend/data")
EXCELS_DIR = DATA_DIR / "excels"
EXCELS_DIR.mkdir(parents=True, exist_ok=True)

SESSION_STORE_PATH = DATA_DIR / "session_state.json"
SESSION_STATE: Dict[str, Dict[str, Optional[str]]] = load_session_state()
store = ExcelStore(EXCELS_DIR)

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)


@app.post("/api/state", response_model=SessionState)
def set_state(payload: dict, request: Request, response: Response):
    sid = get_or_create_sid(request, response)
    SESSION_STATE[sid] = {
        "excel_id": payload.get("excel_id"),
        "sub_name": payload.get("sub_name"),
        "selected_id": payload.get("selected_id"),
    }
    save_session_state()
    return SessionState(**SESSION_STATE[sid])



@app.get("/api/state", response_model=SessionState)
def get_state(request: Request, response: Response):
    sid = get_or_create_sid(request, response)
    return SessionState(**SESSION_STATE.get(sid, {}))


@app.get("/", response_class=HTMLResponse)
def sub_page(request: Request):
    return templates.TemplateResponse("sub_layout.html", {"request": request, "title": "SUB 구성도"})


@app.get("/summary", response_class=HTMLResponse)
def summary_page(request: Request):
    return templates.TemplateResponse("summary.html", {"request": request, "title": "작업시간 분석표"})


@app.get("/api/excels", response_model=List[ExcelInfo])
def list_excels():
    return store.list_excels()


@app.post("/api/excels", response_model=ExcelUploadResponse)
async def upload_excel(file: UploadFile = File(...), request: Request = None, response: Response = None):
    contents = await file.read()
    try:
        tree = parse_uploaded_excel(contents)
        result = store.create_excel(filename=file.filename or "uploaded.xlsx", excel_bytes=contents, tree=tree)

        # 업로드 직후, 세션의 기본 excel_id/sub_name도 세팅해두면 UI가 편합니다.
        if request is not None and response is not None:
            sid = get_or_create_sid(request, response)
            SESSION_STATE[sid] = {
                "excel_id": result.excel_id,
                "sub_name": (result.subs[0] if result.subs else None),
                "selected_id": None,
            }
        save_session_state()

        return result
    except HTTPException:
        raise
    except Exception as e:
        print("Excel parsing error:", e)
        raise HTTPException(status_code=400, detail="엑셀 파싱 실패")


@app.get("/api/excels/{excel_id}/subs", response_model=List[str])
def get_sub_list_for_excel(excel_id: str):
    return store.get_sub_list(excel_id)


@app.get("/api/excels/{excel_id}/subs/{sub_name}/tree", response_model=SubTree)
def get_sub_tree(excel_id: str, sub_name: str):
    return store.get_tree(excel_id, sub_name)


@app.post("/api/excels/{excel_id}/upload_excel", response_model=SubTree)
async def upload_excel_into_existing(excel_id: str, file: UploadFile = File(...)):
    contents = await file.read()
    try:
        parsed_tree = parse_uploaded_excel(contents)

        # 업로드된 파일 자체도 해당 excel_id 디렉토리에 덮어쓸지 여부는 선택입니다.
        # 지금은 "같은 excel_id에 엑셀 재업로드"가 필요할 수 있어서 덮어쓰도록 했습니다.
        p = store._ensure_dir(excel_id)
        p.excel_path.write_bytes(contents)

        return store.upsert_tree_from_upload(excel_id, parsed_tree)
    except HTTPException:
        raise
    except Exception as e:
        print("Excel parsing error:", e)
        raise HTTPException(status_code=400, detail="엑셀 파싱 실패")


@app.patch("/api/excels/{excel_id}/subs/{sub_name}/nodes/{node_id}", response_model=SubTree)
def patch_node(excel_id: str, sub_name: str, node_id: str, patch: SubNodePatch):
    return store.patch_node(excel_id, sub_name, node_id, patch)


@app.post("/api/excels/{excel_id}/save", response_model=dict)
def save_tree_now(excel_id: str):
    store.save_now(excel_id)
    return {"ok": True}


# 하위 호환용 엔드포인트
# 프론트가 아직 /api/subs, /api/subs/{sub}/tree 를 쓰고 있으면,
# 세션에 잡힌 excel_id 기준으로 동작하게 만들어서 단계적으로 마이그레이션 가능하게 합니다.

@app.get("/api/subs", response_model=List[str])
def legacy_get_sub_list(request: Request, response: Response):
    sid = get_or_create_sid(request, response)
    st = SESSION_STATE.get(sid, {})
    excel_id = st.get("excel_id")
    if not excel_id:
        # 예전 동작을 그대로 유지하면 list_sub_names()를 내보내는 게 맞지만,
        # 멀티 엑셀로 넘어가면 excel_id가 없는 상태는 사실상 "엑셀 미업로드"입니다.
        return []
    return store.get_sub_list(excel_id)


@app.get("/api/subs/{sub_name}/tree", response_model=SubTree)
def legacy_get_sub_tree(sub_name: str, request: Request, response: Response):
    sid = get_or_create_sid(request, response)
    st = SESSION_STATE.get(sid, {})
    excel_id = st.get("excel_id")
    if not excel_id:
        excels = store.list_excels()
        if not excels:
            raise HTTPException(status_code=400, detail="엑셀이 없습니다")
        excel_id = excels[0].excel_id
    return store.get_tree(excel_id, sub_name)


@app.patch("/api/subs/{sub_name}/nodes/{node_id}", response_model=SubTree)
def legacy_patch_node(sub_name: str, node_id: str, patch: SubNodePatch, request: Request, response: Response):
    sid = get_or_create_sid(request, response)
    st = SESSION_STATE.get(sid, {})
    excel_id = st.get("excel_id")
    if not excel_id:
        raise HTTPException(status_code=400, detail="엑셀을 먼저 업로드하세요")
    return store.patch_node(excel_id, sub_name, node_id, patch)


@app.post("/api/subs/{sub_name}/save", response_model=dict)
def legacy_save_tree_now(sub_name: str, request: Request, response: Response):
    sid = get_or_create_sid(request, response)
    st = SESSION_STATE.get(sid, {})
    excel_id = st.get("excel_id")
    if not excel_id:
        raise HTTPException(status_code=400, detail="엑셀을 먼저 업로드하세요")
    store.save_now(excel_id)
    return {"ok": True}