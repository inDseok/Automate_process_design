// summary.js
// 요약 화면 전용 스크립트
// sub.js에서 관리하는 currentTree를 그대로 활용함

// 요약 테이블 업데이트 함수
function updateSummaryView() {
    const tbody = document.getElementById("summary-table-body");
    tbody.innerHTML = "";
  
    // 트리가 없으면 안내 메시지 출력
    if (!window.currentTree || !Array.isArray(window.currentTree.nodes) || window.currentTree.nodes.length === 0) {
      const tr = document.createElement("tr");
      const td = document.createElement("td");
      td.colSpan = 6;
      td.textContent = "SUB 단위 부품 구성도 화면에서 데이터를 불러오면 요약 정보가 표시됩니다.";
      tr.appendChild(td);
      tbody.appendChild(tr);
      return;
    }
  
    const nodes = window.currentTree.nodes.slice();
  
    // id -> node 매핑
    const idToNode = {};
    const parentMap = {}; // child.id -> parent.id
    nodes.forEach(n => {
      idToNode[n.id] = n;
      if (n.parent_id !== null && n.parent_id !== undefined) {
        parentMap[n.id] = n.parent_id;
      }
    });
  
    // order 기준 정렬
    nodes
      .slice()
      .sort((a, b) => (a.order ?? 0) - (b.order ?? 0))
      .forEach((node, index) => {
        const tr = document.createElement("tr");
  
        const tdNo = document.createElement("td");
        tdNo.textContent = index + 1;
  
        const tdName = document.createElement("td");
        tdName.textContent = node.name ?? "";
  
        const tdType = document.createElement("td");
        tdType.textContent = node.type ?? "";
  
        const tdVehicle = document.createElement("td");
        tdVehicle.textContent = node.vehicle ?? "";
  
        const tdQty = document.createElement("td");
        tdQty.textContent = node.qty != null ? node.qty + "EA" : "";
  
        // 부모 이름
        const parentId = parentMap[node.id];
        let parentName = "";
        if (parentId && idToNode[parentId]) {
          parentName = idToNode[parentId].name ?? "";
        }
        const tdParent = document.createElement("td");
        tdParent.textContent = parentName;
  
        tr.appendChild(tdNo);
        tr.appendChild(tdName);
        tr.appendChild(tdType);
        tr.appendChild(tdVehicle);
        tr.appendChild(tdQty);
        tr.appendChild(tdParent);
  
        tbody.appendChild(tr);
      });
  }
  
  // 요약 페이지가 열릴 때 자동 업데이트
  window.addEventListener("DOMContentLoaded", () => {
    const summaryContainer = document.getElementById("summary-table-body");
    if (summaryContainer) {
      updateSummaryView();
    }
  });
  
  // 다른 스크립트에서 수동 호출 가능하도록 export
  window.updateSummaryView = updateSummaryView;
  