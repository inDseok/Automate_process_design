from typing import List, Dict
from pathlib import Path
import json
from threading import RLock

from fastapi import FastAPI, HTTPException, Request, Response, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from backend.models import SubTree, SubNodePatch
from backend.excel_loader import list_sub_names, load_sub_tree, parse_uploaded_excel

from uuid import uuid4
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

DATA_DIR = Path("backend/data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
STORE_PATH = DATA_DIR / "tree_store.json"

LOCK = RLock()
TREE_STORE: Dict[str, SubTree] = {}

SESSION_COOKIE = "sid"

# session_id -> { "sub_name": str | None, "selected_id": str | None }
SESSION_STATE = {}

def load_store_from_disk():
    if not STORE_PATH.exists():
        return
    try:
        raw = json.loads(STORE_PATH.read_text(encoding="utf-8"))
        for sub_name, tree_obj in raw.items():
            TREE_STORE[sub_name] = SubTree.model_validate(tree_obj)
    except Exception as e:
        print("STORE 로딩 실패:", e)


def save_store_to_disk():
    try:
        raw = {k: v.model_dump() for k, v in TREE_STORE.items()}
        STORE_PATH.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print("STORE 저장 실패:", e)


def merge_user_edits(base_tree: SubTree, saved_tree: SubTree) -> SubTree:
    # base_tree: 이번 업로드/파싱 결과
    # saved_tree: 서버에 저장되어 있던 사용자 수정값
    saved_map = {n.id: n for n in saved_tree.nodes}

    for i, n in enumerate(base_tree.nodes):
        if n.id in saved_map:
            sn = saved_map[n.id]
            # 사용자 수정값 유지: name, type, vehicle, material, qty
            base_tree.nodes[i].name = sn.name
            base_tree.nodes[i].type = sn.type
            base_tree.nodes[i].vehicle = sn.vehicle
            base_tree.nodes[i].material = sn.material
            base_tree.nodes[i].qty = sn.qty

    return base_tree


load_store_from_disk()


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)

from uuid import uuid4

SESSION_COOKIE = "sid"
SESSION_STATE = {}  # sid -> {"sub_name": str|None, "selected_id": str|None}

def get_or_create_sid(request: Request, response: Response) -> str:
    sid = request.cookies.get(SESSION_COOKIE)
    if not sid:
        sid = str(uuid4())
        response.set_cookie(
            key=SESSION_COOKIE,
            value=sid,
            httponly=True,
            samesite="lax"
        )
    return sid

@app.get("/api/state")
def get_state(request: Request, response: Response):
    sid = get_or_create_sid(request, response)
    return SESSION_STATE.get(sid, {"sub_name": None, "selected_id": None})

@app.post("/api/state")
def set_state(payload: dict, request: Request, response: Response):
    sid = get_or_create_sid(request, response)
    SESSION_STATE[sid] = {
        "sub_name": payload.get("sub_name"),
        "selected_id": payload.get("selected_id")
    }
    return SESSION_STATE[sid]


@app.get("/", response_class=HTMLResponse)
def sub_page(request: Request):
    return templates.TemplateResponse("sub_layout.html", {"request": request, "title": "SUB 구성도"})


@app.get("/summary", response_class=HTMLResponse)
def summary_page(request: Request):
    return templates.TemplateResponse("summary.html", {"request": request, "title": "작업시간 분석표"})


@app.get("/api/subs", response_model=List[str])
def get_sub_list():
    return list_sub_names()


@app.get("/api/subs/{sub_name}/tree", response_model=SubTree)
def get_sub_tree(sub_name: str):
    sub_list = list_sub_names()
    if sub_name not in sub_list:
        raise HTTPException(status_code=404, detail="Unknown SUB name")

    with LOCK:
        if sub_name in TREE_STORE:
            return TREE_STORE[sub_name]

        tree = load_sub_tree(sub_name)
        TREE_STORE[sub_name] = tree
        save_store_to_disk()
        return tree


@app.post("/api/upload_excel", response_model=SubTree)
async def upload_excel(file: UploadFile = File(...)):
    contents = await file.read()
    try:
        new_tree = parse_uploaded_excel(contents)

        with LOCK:
            if new_tree.sub_name in TREE_STORE:
                new_tree = merge_user_edits(new_tree, TREE_STORE[new_tree.sub_name])

            TREE_STORE[new_tree.sub_name] = new_tree
            save_store_to_disk()

        return new_tree

    except Exception as e:
        print("Excel parsing error:", e)
        raise HTTPException(status_code=400, detail="엑셀 파싱 실패")


@app.patch("/api/subs/{sub_name}/nodes/{node_id}", response_model=SubTree)
def patch_node(sub_name: str, node_id: str, patch: SubNodePatch):
    with LOCK:
        if sub_name not in TREE_STORE:
            raise HTTPException(status_code=404, detail="Tree not loaded")

        tree = TREE_STORE[sub_name]

        idx = None
        for i, n in enumerate(tree.nodes):
            if n.id == node_id:
                idx = i
                break
        if idx is None:
            raise HTTPException(status_code=404, detail="Node not found")

        node = tree.nodes[idx]
        data = patch.model_dump(exclude_unset=True)

        for k, v in data.items():
            setattr(node, k, v)

        tree.nodes[idx] = node
        TREE_STORE[sub_name] = tree
        save_store_to_disk()

        return tree


@app.post("/api/subs/{sub_name}/save", response_model=SubTree)
def save_tree_now(sub_name: str):
    # 명시적으로 저장 버튼을 붙일 때 쓰기 좋게 남겨둔 엔드포인트
    with LOCK:
        if sub_name not in TREE_STORE:
            raise HTTPException(status_code=404, detail="Tree not loaded")
        save_store_to_disk()
        return TREE_STORE[sub_name]
