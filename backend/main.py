from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Dict, List, Optional, Any

import json
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, Response, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from pydantic import BaseModel

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

DATA_DIR = Path("backend/data")
EXCELS_DIR = DATA_DIR / "excels"
EXCELS_DIR.mkdir(parents=True, exist_ok=True)

SESSION_COOKIE = "sid"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ExcelUploadResponse(BaseModel):
    excel_id: str
    filename: str
    subs: List[str]


class ExcelInfo(BaseModel):
    excel_id: str
    filename: str
    uploaded_at: Optional[str] = None
    subs: List[str] = []


class SessionState(BaseModel):
    excel_id: Optional[str] = None
    sub_name: Optional[str] = None
    selected_id: Optional[str] = None


def merge_user_edits(base_tree: SubTree, saved_tree: SubTree) -> SubTree:
    saved_map = {n.id: n for n in saved_tree.nodes}

    for i, n in enumerate(base_tree.nodes):
        if n.id in saved_map:
            sn = saved_map[n.id]
            base_tree.nodes[i].name = sn.name
            base_tree.nodes[i].type = sn.type
            base_tree.nodes[i].vehicle = sn.vehicle
            base_tree.nodes[i].material = sn.material
            base_tree.nodes[i].qty = sn.qty

    return base_tree


@dataclass
class ExcelStorePaths:
    root: Path
    meta_path: Path
    tree_store_path: Path
    excel_path: Path


class ExcelStore:
    """
    excel_id 단위로 분리된 저장소

    디스크 구조
    backend/data/excels/{excel_id}/
      meta.json
      tree_store.json
      uploaded.xlsx
    """

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.lock = RLock()

        self._trees: Dict[str, Dict[str, SubTree]] = {}  # excel_id -> { sub_name -> SubTree }
        self._meta: Dict[str, Dict[str, Any]] = {}        # excel_id -> meta dict

    def _paths(self, excel_id: str) -> ExcelStorePaths:
        root = self.base_dir / excel_id
        return ExcelStorePaths(
            root=root,
            meta_path=root / "meta.json",
            tree_store_path=root / "tree_store.json",
            excel_path=root / "uploaded.xlsx",
        )

    def _ensure_dir(self, excel_id: str) -> ExcelStorePaths:
        p = self._paths(excel_id)
        p.root.mkdir(parents=True, exist_ok=True)
        return p

    def _load_meta_from_disk(self, excel_id: str) -> Dict[str, Any]:
        p = self._paths(excel_id)
        if not p.meta_path.exists():
            return {}
        try:
            return json.loads(p.meta_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save_meta_to_disk(self, excel_id: str, meta: Dict[str, Any]) -> None:
        p = self._ensure_dir(excel_id)
        try:
            p.meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            print("META 저장 실패:", e)

    def _load_trees_from_disk(self, excel_id: str) -> Dict[str, SubTree]:
        p = self._paths(excel_id)
        if not p.tree_store_path.exists():
            return {}
        try:
            raw = json.loads(p.tree_store_path.read_text(encoding="utf-8"))
            out: Dict[str, SubTree] = {}
            for sub_name, tree_obj in raw.items():
                out[sub_name] = SubTree.model_validate(tree_obj)
            return out
        except Exception as e:
            print("TREE_STORE 로딩 실패:", e)
            return {}

    def _save_trees_to_disk(self, excel_id: str, trees: Dict[str, SubTree]) -> None:
        p = self._ensure_dir(excel_id)
        try:
            raw = {k: v.model_dump() for k, v in trees.items()}
            p.tree_store_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            print("TREE_STORE 저장 실패:", e)

    def _warm_cache(self, excel_id: str) -> None:
        if excel_id not in self._trees:
            self._trees[excel_id] = self._load_trees_from_disk(excel_id)
        if excel_id not in self._meta:
            self._meta[excel_id] = self._load_meta_from_disk(excel_id)

    def list_excels(self) -> List[ExcelInfo]:
        infos: List[ExcelInfo] = []
        if not self.base_dir.exists():
            return infos

        for d in self.base_dir.iterdir():
            if not d.is_dir():
                continue
            excel_id = d.name
            meta = self._load_meta_from_disk(excel_id)
            subs = []
            try:
                trees = self._load_trees_from_disk(excel_id)
                subs = sorted(list(trees.keys()))
            except Exception:
                subs = []

            infos.append(
                ExcelInfo(
                    excel_id=excel_id,
                    filename=str(meta.get("filename") or meta.get("original_filename") or ""),
                    uploaded_at=meta.get("uploaded_at"),
                    subs=subs,
                )
            )

        infos.sort(key=lambda x: (x.uploaded_at or "", x.excel_id), reverse=True)
        return infos

    def create_excel(self, filename: str, excel_bytes: bytes, tree: SubTree) -> ExcelUploadResponse:
        with self.lock:
            excel_id = str(uuid4())
            p = self._ensure_dir(excel_id)

            try:
                p.excel_path.write_bytes(excel_bytes)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"엑셀 저장 실패: {e}")

            meta = {
                "excel_id": excel_id,
                "filename": filename,
                "uploaded_at": utc_now_iso(),
            }
            self._meta[excel_id] = meta
            self._save_meta_to_disk(excel_id, meta)

            self._trees[excel_id] = {tree.sub_name: tree}
            self._save_trees_to_disk(excel_id, self._trees[excel_id])

            return ExcelUploadResponse(excel_id=excel_id, filename=filename, subs=[tree.sub_name])

    def get_sub_list(self, excel_id: str) -> List[str]:
        with self.lock:
            self._warm_cache(excel_id)
            return sorted(list(self._trees.get(excel_id, {}).keys()))

    def get_tree(self, excel_id: str, sub_name: str) -> SubTree:
        with self.lock:
            self._warm_cache(excel_id)

            trees = self._trees.get(excel_id)
            if trees is None:
                raise HTTPException(status_code=404, detail="Unknown excel_id")

            if sub_name in trees:
                return trees[sub_name]

            # 여기 로직은 기존 load_sub_tree를 유지하되,
            # 멀티 엑셀 환경에서는 excel_id에 매핑된 엑셀 파일을 기반으로 파싱해야 정상입니다.
            # 현재 excel_loader 시그니처를 바꾸지 않는 선에서, 일단 기존 동작 유지합니다.
            sub_list = list_sub_names()
            if sub_name not in sub_list:
                raise HTTPException(status_code=404, detail="Unknown SUB name")

            tree = load_sub_tree(sub_name)
            trees[sub_name] = tree
            self._save_trees_to_disk(excel_id, trees)
            return tree

    def upsert_tree_from_upload(self, excel_id: str, parsed_tree: SubTree) -> SubTree:
        with self.lock:
            self._warm_cache(excel_id)
            if excel_id not in self._trees:
                raise HTTPException(status_code=404, detail="Unknown excel_id")

            trees = self._trees[excel_id]
            if parsed_tree.sub_name in trees:
                parsed_tree = merge_user_edits(parsed_tree, trees[parsed_tree.sub_name])

            trees[parsed_tree.sub_name] = parsed_tree
            self._save_trees_to_disk(excel_id, trees)
            return parsed_tree

    def patch_node(self, excel_id: str, sub_name: str, node_id: str, patch: SubNodePatch) -> SubTree:
        with self.lock:
            self._warm_cache(excel_id)
            trees = self._trees.get(excel_id)
            if not trees:
                raise HTTPException(status_code=404, detail="Unknown excel_id")

            if sub_name not in trees:
                raise HTTPException(status_code=404, detail="Tree not loaded")

            tree = trees[sub_name]

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
            trees[sub_name] = tree
            self._save_trees_to_disk(excel_id, trees)
            return tree

    def save_now(self, excel_id: str) -> None:
        with self.lock:
            self._warm_cache(excel_id)
            trees = self._trees.get(excel_id)
            if trees is None:
                raise HTTPException(status_code=404, detail="Unknown excel_id")
            self._save_trees_to_disk(excel_id, trees)


store = ExcelStore(EXCELS_DIR)


def get_or_create_sid(request: Request, response: Response) -> str:
    sid = request.cookies.get(SESSION_COOKIE)
    if not sid:
        sid = str(uuid4())
        response.set_cookie(
            key=SESSION_COOKIE,
            value=sid,
            httponly=True,
            samesite="lax",
        )
    return sid


SESSION_STORE_PATH = DATA_DIR / "session_state.json"

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

SESSION_STATE: Dict[str, Dict[str, Optional[str]]] = load_session_state()


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
