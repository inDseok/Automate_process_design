from typing import Optional, List
from pydantic import BaseModel


class SubNode(BaseModel):
    id: str
    parent_id: Optional[str] = None
    order: int
    type: str                # ASSY / PART 등
    name: str                # 부품명
    part_no: Optional[str] = None  # 품번
    material: Optional[str] = None # 재질
    qty: Optional[float] = None    # 수량


class SubTree(BaseModel):
    sub_name: str
    nodes: List[SubNode]

class SubNodePatch(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    part_no: Optional[str] = None
    material: Optional[str] = None
    qty: Optional[float] = None