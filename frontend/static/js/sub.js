document.addEventListener("DOMContentLoaded", () => {
  const API_BASE = "http://localhost:8000";

  const btnReload = document.getElementById("btn-reload-sub");
  const fileInput = document.getElementById("excel-file");
  const caption = document.getElementById("tree-caption");

  const modal = document.getElementById("spec-modal");
  const specList = document.getElementById("spec-list");
  const btnApply = document.getElementById("btn-spec-apply");
  const btnCancel = document.getElementById("btn-spec-cancel");

  let selectedSpecName = null;


  /* =========================
     1. 불러오기 → 파일 선택
     ========================= */
  if (btnReload && fileInput) {
    btnReload.addEventListener("click", (e) => {
      e.preventDefault();
      fileInput.value = "";
      fileInput.click();
    });
  }

  /* =========================
     2. 파일 선택됨
     ========================= */
  if (fileInput) {
    fileInput.addEventListener("change", async () => {
      if (!fileInput.files.length) return;
      const file = fileInput.files[0];
      await handleBomFile(file);
    });
  }

  /* =========================
     3. BOM → 사양 추출
     ========================= */
     async function handleBomFile(file) {
      if (caption) caption.textContent = "사양 추출 중...";
    
      const formData = new FormData();
      formData.append("file", file);
    
      try {
        const res = await fetch(API_BASE + "/api/bom/upload", {
          method: "POST",
          body: formData
        });
    
        console.log("spec api status =", res.status);
    
        if (!res.ok) {
          throw new Error("사양 추출 실패");
        }
    
        const data = await res.json();
    
        if (caption) caption.textContent = "사양 선택 대기 중...";
    
        openSpecModal(data.spec_info);
        window.currentBomId = data.bom_id;
    
      } catch (err) {
        console.error(err);
        if (caption) caption.textContent = "사양 추출 실패";
        alert("사양 추출에 실패했습니다. 서버 로그를 확인하세요.");
      }
    }
    

  /* =========================
     4. 사양 선택 모달
     ========================= */
  function openSpecModal(specData) {
    specList.innerHTML = "";
    selectedSpecCol = null;

    (specData.sheets || []).forEach(sheet => {
      const title = document.createElement("div");
      title.textContent = sheet.sheet;
      title.style.fontWeight = "600";
      title.style.margin = "10px 0 6px";
      specList.appendChild(title);

      (sheet.specs || []).forEach(spec => {
        const label = document.createElement("label");
        label.style.display = "block";
        label.style.fontSize = "13px";
        label.style.marginBottom = "6px";

        const radio = document.createElement("input");
        radio.type = "radio";
        radio.name = "spec";
        radio.value = spec.col;

        radio.dataset.specName = spec.spec_name;

        radio.addEventListener("change", () => {
          selectedSpecCol = Number(spec.col);
          selectedSpecName = spec.spec_name;
        });

        label.appendChild(radio);
        label.append(" " + spec.spec_name);

        specList.appendChild(label);
      });
    });

    modal.style.display = "flex";
  }

  /* =========================
     5. 모달 버튼
     ========================= */
  if (btnCancel) {
    btnCancel.addEventListener("click", (e) => {
      e.preventDefault();
      modal.style.display = "none";
      if (caption) caption.textContent = "사양 선택 취소됨";
    });
  }

  if (btnApply) {
    btnApply.addEventListener("click", async (e) => {
      e.preventDefault();
    
      if (!selectedSpecName) {
        alert("사양을 선택하세요.");
        return;
      }
    
      modal.style.display = "none";
      caption.textContent = `선택된 사양 = ${selectedSpecName}`;
    
      await loadTreeForSelectedSpec();
    });
  
  }
  
  function normalizeTreeTypes(tree) {
    if (!tree || !Array.isArray(tree.nodes)) return tree;
  
    tree.nodes = tree.nodes.map(n => ({
      ...n,
      // id는 그대로 둔다 (string)
      id: String(n.id),
      parent_id:
        n.parent_id === null || n.parent_id === undefined
          ? null
          : String(n.parent_id),
      order:
        n.order === null || n.order === undefined || n.order === ""
          ? 0
          : Number(n.order),
    }));
  
    return tree;
  }

  
  async function loadTreeForSelectedSpec() {
    if (!currentBomId) {
      alert("BOM이 선택되지 않았습니다.");
      return;
    }
  
    if (!selectedSpecName) {
      alert("사양이 선택되지 않았습니다.");
      return;
    }
  
    try {
      caption.textContent = "트리 생성 중...";
  
      const url = `${API_BASE}/api/bom/${currentBomId}/tree?spec=${encodeURIComponent(selectedSpecName)}`;
  
      const res = await fetch(url);
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "트리 로드 실패");
      }
  
      const tree = await res.json();
      console.log("TREE RAW =", tree);
      // 타입 보정 (기존에 쓰던 로직 있으면 그대로 재사용)
      currentTree = normalizeTreeTypes ? normalizeTreeTypes(tree) : tree;
  
      // 선택 상태 초기화
      currentSelectedId = null;
  
      // 실제 트리 렌더링
      renderSubTree(currentTree);
  
      caption.textContent = `트리 로드 완료 (${selectedSpecName})`;
    } catch (e) {
      console.error(e);
      caption.textContent = "트리 로드 실패";
      alert(e.message);
    }
  }
  
  // =========================
  // Tree Rendering
  // =========================

  function adjustTreeLines() {
    const containers = document.querySelectorAll("#sub-tree-root .tree-children");

    containers.forEach(container => {
      const rows = [];
      container.childNodes.forEach(child => {
        if (child.nodeType === Node.ELEMENT_NODE && child.classList.contains("tree-node")) {
          const row = child.querySelector(".tree-node-row");
          if (row) rows.push(row);
        }
      });

      if (rows.length === 0) {
        container.style.removeProperty("--line-top");
        container.style.removeProperty("--line-height");
        return;
      }

      const parentRect = container.getBoundingClientRect();
      const firstRect = rows[0].getBoundingClientRect();
      const lastRect = rows[rows.length - 1].getBoundingClientRect();

      const firstMid = firstRect.top + firstRect.height / 2 - parentRect.top;
      const lastMid = lastRect.top + lastRect.height / 2 - parentRect.top;

      container.style.setProperty("--line-top", firstMid + "px");
      container.style.setProperty("--line-height", Math.max(0, lastMid - firstMid) + "px");
    });
  }

  function updateDetailPanel() {
    const empty = document.getElementById("detail-empty");
    const form = document.getElementById("detail-form");
    if (!empty || !form) return;

    if (!currentTree || !currentSelectedId) {
      empty.style.display = "block";
      form.style.display = "none";
      return;
    }

    const node = currentTree.nodes?.find(n => String(n.id) === String(currentSelectedId));
    if (!node) {
      empty.style.display = "block";
      form.style.display = "none";
      return;
    }

    empty.style.display = "none";
    form.style.display = "block";

    const setVal = (id, v) => {
      const el = document.getElementById(id);
      if (el) el.value = (v ?? "");
    };

    setVal("detail-id", node.id);
    setVal("detail-name", node.name);
    setVal("detail-type", node.type);
    setVal("detail-part_no", node.part_no);
    setVal("detail-material", node.material);
    setVal("detail-qty", node.qty);
  }

  function renderSubTree() {
    const container = document.getElementById("sub-tree-root");
    if (!container) return;

    container.innerHTML = "";
    currentSelectedId = null;
    updateDetailPanel();

    if (!currentTree || !Array.isArray(currentTree.nodes) || currentTree.nodes.length === 0) {
      const span = document.createElement("span");
      span.textContent = "트리 데이터가 없습니다.";
      span.style.fontSize = "12px";
      span.style.color = "#666";
      container.appendChild(span);
      return;
    }

    const nodes = currentTree.nodes;

    const childMap = {};
    nodes.forEach(n => {
      if (n.id === n.parent_id) {
        console.error("SELF PARENT NODE:", n);
      }
      const pid = (n.parent_id === null || n.parent_id === undefined) ? "ROOT" : n.parent_id;
      if (!childMap[pid]) childMap[pid] = [];
      childMap[pid].push(n);
    });

    Object.keys(childMap).forEach(key => {
      childMap[key].sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
    });

    function createNodeCard(node) {
      const card = document.createElement("div");
  
      const classNames = ["node-card"];
  
      if (node.type === "ASSY") {
          classNames.push("assy");
      }
  
      if (node.type === "외주") {
          classNames.push("outsource");
      }
  
      card.className = classNames.join(" ");
      card.dataset.nodeId = node.id;
  
      // -----------------
      // 제목 (부품명)
      // -----------------
      const title = document.createElement("div");
      title.className = "node-card-title";
      title.textContent = node.name || "(이름 없음)";
      card.appendChild(title);
  
      // -----------------
      // 메타 영역 (3줄 고정)
      // -----------------
      const meta = document.createElement("div");
      meta.className = "node-card-meta";
  
      // 품번
      const partLine = document.createElement("div");
      partLine.className = "meta-line";
      partLine.textContent = `품번: ${node.part_no ?? "-"}`;
      meta.appendChild(partLine);
  
      // 재질
      const materialLine = document.createElement("div");
      materialLine.className = "meta-line";
      materialLine.textContent = `재질: ${node.material ?? "-"}`;
      meta.appendChild(materialLine);
  
      // 수량
      const qtyLine = document.createElement("div");
      qtyLine.className = "meta-line";
      qtyLine.textContent =
          node.qty !== null && node.qty !== undefined
              ? `수량: ${node.qty}EA`
              : "수량: -";
      meta.appendChild(qtyLine);
  
      card.appendChild(meta);
  
      // -----------------
      // 타입 배지
      // -----------------
      const badge = document.createElement("div");
      badge.className = "node-badge" + (node.type === "ASSY" ? " assy" : "");
      badge.textContent = node.type || "NODE";
      card.appendChild(badge);
  
      // -----------------
      // 클릭 이벤트
      // -----------------
      card.addEventListener("click", async (e) => {
          e.stopPropagation();
  
          currentSelectedId = node.id;
          updateSelectionHighlight();
          updateDetailPanel();
  
          if (currentTree) {
              try {
                  await saveSessionState(currentTree.sub_name, String(node.id));
              } catch (err) {
                  console.error("세션 저장 실패:", err);
              }
          }
      });
  
      return card;
    }

    function createNodeWrapper(node, depth) {
      const wrapper = document.createElement("div");
      wrapper.className = "tree-node depth-" + depth;

      const row = document.createElement("div");
      row.className = "tree-node-row";

      const card = createNodeCard(node);
      row.appendChild(card);
      wrapper.appendChild(row);

      const children = childMap[node.id] || [];
      if (children.length > 0) {
        const childrenContainer = document.createElement("div");
        childrenContainer.className = "tree-children";

        children.forEach(child => {
          childrenContainer.appendChild(createNodeWrapper(child, depth + 1));
        });

        wrapper.appendChild(childrenContainer);
      }

      return wrapper;
    }

    const roots = childMap["ROOT"] || [];
    roots.forEach(rootNode => {
      container.appendChild(createNodeWrapper(rootNode, 0));
    });

    requestAnimationFrame(adjustTreeLines);
  }

  // =========================
  // Event bindings to USE the functions
  // =========================

  function bindDetailPanelEvents() {
      const btnApply = document.getElementById("btn-apply-local");
      const btnClear = document.getElementById("btn-clear-selection");
    
      if (btnApply) btnApply.addEventListener("click", (e) => { e.preventDefault(); applyAndPersistSelectedNode(); });
      if (btnClear) btnClear.addEventListener("click", async (e) => {
        e.preventDefault();
        clearSelection();
        await saveSessionState(currentTree?.sub_name ?? null, null);
      });
  }
    

  function bindClearOnBackgroundClick() {
    const root = document.getElementById("sub-tree-root");
    if (!root) return;

    // 트리 빈 공간 클릭 시 선택 해제
    root.addEventListener("click", () => {
      clearSelection();
    });
  }

  // =========================
  // Buttons
  // =========================
  async function saveSessionState(subName, selectedId) {
    if (!currentExcelId) return;
  
    try {
      await fetch(API_BASE + "/api/state", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          excel_id: currentExcelId,
          sub_name: subName,
          selected_id: selectedId
        })
      });
    } catch (e) {
      console.error("세션 상태 저장 실패:", e);
    }
  }
  
  
  const btnExpandAll = document.getElementById("btn-expand-all");
  if (btnExpandAll) btnExpandAll.addEventListener("click", renderSubTree);

  // =========================
  // Init
  // =========================

  bindDetailPanelEvents();
  bindClearOnBackgroundClick();

  async function applyAndPersistSelectedNode() {
      if (!currentTree || currentSelectedId == null) return;
    
      const subName = currentTree.sub_name;
      const nodeId = String(currentSelectedId);
    
      const payload = {
        name: document.getElementById("detail-name").value,
        type: document.getElementById("detail-type").value,
        part_no: document.getElementById("detail-part_no").value || null,
        material: document.getElementById("detail-material").value || null,
        qty: (() => {
          const v = document.getElementById("detail-qty").value;
          return v === "" ? null : Number(v);
        })()
      };
    
      const res = await fetch(
        `${API_BASE}/api/excels/${currentExcelId}/subs/${currentTree.sub_name}/nodes/${currentSelectedId}`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        }
      );
    
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg);
      }
    
      // 서버가 갱신된 트리를 내려주므로, 그걸 currentTree로 교체
      currentTree = await res.json();
    
      // 화면 리렌더
      renderSubTree();
    
      // 선택 유지
      currentSelectedId = nodeId;
      updateDetailPanel();
    }
    
    document.getElementById("btn-apply-local").addEventListener("click", async (e) => {
      e.preventDefault();
      try {
        await applyAndPersistSelectedNode();
        // 필요하면 성공 토스트 같은 UX를 여기서 처리
      } catch (err) {
        console.error(err);
        alert("저장 실패. 콘솔을 확인하세요.");
      }
    });
    document.getElementById("btn-clear-selection").addEventListener("click", async () => {
      currentSelectedId = null;
      updateDetailPanel();
  
      await fetch(API_BASE + "/api/state", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({
              sub_name: currentTree?.sub_name ?? null,
              selected_id: null
          })
      });
  });
  
  //세션 생성
  async function restoreSessionState() {
    try {
      const res = await fetch(API_BASE + "/api/state", {
        credentials: "include"
      });
      if (!res.ok) return;
  
      const state = await res.json();
      if (!state.excel_id || !state.sub_name) return;
  
      currentExcelId = state.excel_id;
  
      const treeRes = await fetch(
        `${API_BASE}/api/excels/${state.excel_id}/subs/${state.sub_name}/tree`,
        { credentials: "include" }
      );
      if (!treeRes.ok) return;
  
      currentTree = await treeRes.json();
      renderSubTree();
  
      if (state.selected_id) {
        currentSelectedId = state.selected_id;
        updateDetailPanel();
      }
    } catch (e) {
      console.error("세션 상태 복구 실패:", e);
    }
  }
  
  // restoreSessionState();

});