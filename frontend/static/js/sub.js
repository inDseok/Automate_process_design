document.addEventListener("DOMContentLoaded", () => {
    const API_BASE = "http://localhost:8000";
  
    let currentTree = null;
    let currentSelectedId = null;
  
    // =========================
    // Selection / Detail Panel
    // =========================
  
    function updateSelectionHighlight() {
      document.querySelectorAll(".node-card").forEach(card => {
        if (card.dataset.nodeId === String(currentSelectedId)) {
          card.classList.add("selected");
        } else {
          card.classList.remove("selected");
        }
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
      setVal("detail-vehicle", node.vehicle);
      setVal("detail-material", node.material);
      setVal("detail-qty", node.qty);
    }
  
    function clearSelection() {
      currentSelectedId = null;
      updateSelectionHighlight();
      updateDetailPanel();
    }
  
    function applyLocalChanges() {
      if (!currentTree || !currentSelectedId) return;
      const node = currentTree.nodes?.find(n => String(n.id) === String(currentSelectedId));
      if (!node) return;
  
      const getVal = (id) => {
        const el = document.getElementById(id);
        return el ? el.value : "";
      };
  
      node.name = getVal("detail-name");
      node.type = getVal("detail-type");
      node.vehicle = getVal("detail-vehicle");
      node.material = getVal("detail-material");
  
      const qtyVal = getVal("detail-qty").trim();
      node.qty = (qtyVal === "") ? null : Number(qtyVal);
  
      // Re-render and restore selection
      const keepId = node.id;
      renderSubTree();
      currentSelectedId = keepId;
      updateSelectionHighlight();
      updateDetailPanel();
  
      if (typeof refreshJsonPreview === "function") {
        refreshJsonPreview();
      }
    }
  
    // 서버에서 SUB 트리를 다시 로딩 (API가 있을 때만 사용)
    async function loadSubTree() {
      const select = document.getElementById("sub-select");
      const subName = select ? select.value : null;
      if (!subName) return;
  
      const caption = document.getElementById("tree-caption");
      if (caption) caption.textContent = "트리 로딩 중...";
  
      try {
        const res = await fetch(`${API_BASE}/api/subs/${encodeURIComponent(subName)}/tree`);
        if (!res.ok) throw new Error("트리 로딩 실패: " + res.status);
  
        currentTree = await res.json();
  
        if (caption) caption.textContent = `${subName} 트리 로드됨`;
        renderSubTree();
      } catch (err) {
        if (caption) caption.textContent = "트리 로딩 실패";
        console.error(err);
      }
    }
  
    function resetSelectedNode() {
      if (!currentTree || !currentSelectedId) return;
      // 현재 구조에서는 '선택 노드만 원복'보다 '전체 재로딩'이 안전
      loadSubTree();
    }
  
    // =========================
    // Node Card
    // =========================
  
    function createNodeCard(node) {
        const card = document.createElement("div");
        card.className = "node-card" + (node.type === "ASSY" ? " assy" : "");
        card.dataset.nodeId = node.id;
      
        const title = document.createElement("div");
        title.className = "node-card-title";
        title.textContent = node.name || "(이름 없음)";
        card.appendChild(title);
      
        const meta = document.createElement("div");
        meta.className = "node-card-meta";
        const lines = [];
        if (node.vehicle) lines.push("양산처: " + node.vehicle);
        if (node.material) lines.push("재질: " + node.material);
        if (node.qty !== null && node.qty !== undefined) lines.push("수량: " + node.qty + "EA");
        meta.textContent = lines.join(" / ");
        card.appendChild(meta);
      
        const badge = document.createElement("div");
        badge.className = "node-badge" + (node.type === "ASSY" ? " assy" : "");
        badge.textContent = node.type || "NODE";
        card.appendChild(badge);
      
        // 클릭 핸들러는 1개만
        card.addEventListener("click", async (e) => {
          e.stopPropagation();
      
          currentSelectedId = node.id;
          updateSelectionHighlight();
          updateDetailPanel();
      
          // 세션 상태 저장
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
      
  
    // =========================
    // SUB List
    // =========================
  
    async function loadSubList() {
      const select = document.getElementById("sub-select");
      if (!select) return;
  
      select.innerHTML = "";
  
      try {
        const res = await fetch(API_BASE + "/api/subs");
        const subs = await res.json();
  
        subs.forEach(name => {
          const opt = document.createElement("option");
          opt.value = name;
          opt.textContent = name;
          select.appendChild(opt);
        });
  
        // SUB 선택 변경 시 트리 로딩
        select.addEventListener("change", () => {
          clearSelection();
          loadSubTree();
        });
  
      } catch (err) {
        console.error("SUB 목록 로딩 실패:", err);
      }
    }
  
    // =========================
    // Excel Upload
    // =========================
  
    function uploadExcelAndLoadTree() {
      const fileInput = document.getElementById("excel-file");
      if (!fileInput) return;
  
      fileInput.value = "";
      fileInput.click();

    }
    
    async function handleExcelFileSelected(file) {
      const caption = document.getElementById("tree-caption");
      if (caption) caption.textContent = "엑셀 업로드 중...";
  
      const formData = new FormData();
      formData.append("file", file);
  
      try {
        const res = await fetch(API_BASE + "/api/upload_excel", {
          method: "POST",
          body: formData
        });
        if (!res.ok) throw new Error("업로드 실패: " + res.status);
  
        currentTree = await res.json();
  
        if (caption) caption.textContent = `${file.name} 트리 불러옴`;
        renderSubTree();

        await saveSessionState(currentTree.sub_name, null);
      } catch (err) {
        if (caption) caption.textContent = "업로드 실패";
        console.error(err);
      }
    }
  
    function bindExcelInputOnce() {
      const fileInput = document.getElementById("excel-file");
      if (!fileInput) return;
  
      fileInput.addEventListener("change", async () => {
        const file = fileInput.files && fileInput.files[0];
        if (!file) return;
        await handleExcelFileSelected(file);
      });
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
        const pid = (n.parent_id === null || n.parent_id === undefined) ? "ROOT" : n.parent_id;
        if (!childMap[pid]) childMap[pid] = [];
        childMap[pid].push(n);
      });
  
      Object.keys(childMap).forEach(key => {
        childMap[key].sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
      });
  
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
        const btnReset = document.getElementById("btn-reset-node");
        const btnClear = document.getElementById("btn-clear-selection");
      
        if (btnApply) btnApply.addEventListener("click", (e) => { e.preventDefault(); applyAndPersistSelectedNode(); });
        if (btnReset) btnReset.addEventListener("click", (e) => { e.preventDefault(); resetSelectedNode(); });
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
        try {
          await fetch(API_BASE + "/api/state", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              sub_name: subName,
              selected_id: selectedId
            })
          });
        } catch (e) {
          console.error("세션 상태 저장 실패:", e);
        }
    }
    const btnReload = document.getElementById("btn-reload-sub");
    if (btnReload) btnReload.addEventListener("click", uploadExcelAndLoadTree);
    
    const btnExpandAll = document.getElementById("btn-expand-all");
    if (btnExpandAll) btnExpandAll.addEventListener("click", renderSubTree);
  
    // =========================
    // Init
    // =========================
  
    loadSubList();
    bindDetailPanelEvents();
    bindClearOnBackgroundClick();
    bindExcelInputOnce();

    async function applyAndPersistSelectedNode() {
        if (!currentTree || currentSelectedId == null) return;
      
        const subName = currentTree.sub_name;
        const nodeId = String(currentSelectedId);
      
        const payload = {
          name: document.getElementById("detail-name").value,
          type: document.getElementById("detail-type").value,
          vehicle: document.getElementById("detail-vehicle").value || null,
          material: document.getElementById("detail-material").value || null,
          qty: (() => {
            const v = document.getElementById("detail-qty").value;
            return v === "" ? null : Number(v);
          })()
        };
      
        const res = await fetch(
          `${API_BASE}/api/subs/${encodeURIComponent(subName)}/nodes/${encodeURIComponent(nodeId)}`,
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
            body: JSON.stringify({
                sub_name: currentTree?.sub_name ?? null,
                selected_id: null
            })
        });
    });
    
    //세션 생성
      async function restoreSessionState() {
        try {
            const res = await fetch(API_BASE + "/api/state");
            if (!res.ok) return;
    
            const state = await res.json();
            if (!state.sub_name) return;
    
            const treeRes = await fetch(
                API_BASE + "/api/subs/" + encodeURIComponent(state.sub_name) + "/tree"
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
    restoreSessionState();

});
