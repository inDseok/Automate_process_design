import streamlit as st
from streamlit_sortables import sort_items

st.set_page_config(page_title="아이콘 드래그앤드롭 데모", layout="wide")

st.title("아이콘 드래그앤드롭 데모")

# 초기 아이콘 목록 (원하면 여기만 바꿔서 쓰면 됨)
default_icons = [
    "📦 박스적재기",
    "🤖 로봇",
    "⚙️ 설비",
    "🧪 검사기",
    "🧰 공구함",
]

# 세션 상태에 아이콘 저장
if "icon_lists" not in st.session_state:
    st.session_state.icon_lists = [
        {
            "header": "아이콘 창고",
            "items": default_icons.copy(),
        },
        {
            "header": "배치한 아이콘",
            "items": [],
        },
    ]

st.caption("아이콘을 드래그해서 순서를 바꾸거나, 다른 박스로 옮겨보세요.")

# 여러 컨테이너(박스) 사이에서 드래그앤드롭
sorted_lists = sort_items(
    st.session_state.icon_lists,
    multi_containers=True,
    direction="horizontal",   # 가로로 박스 2개 나열
    key="icon_sorter",
)

# 정렬 결과를 세션 상태에 반영
st.session_state.icon_lists = sorted_lists

# 현재 상태 출력
col1, col2 = st.columns(2)

with col1:
    st.subheader("아이콘 창고 상태")
    for i, item in enumerate(st.session_state.icon_lists[0]["items"], start=1):
        st.write(f"{i}. {item}")

with col2:
    st.subheader("배치한 아이콘 상태")
    if st.session_state.icon_lists[1]["items"]:
        for i, item in enumerate(st.session_state.icon_lists[1]["items"], start=1):
            st.write(f"{i}. {item}")
    else:
        st.write("아직 배치한 아이콘이 없습니다.")

# 아래는 단일 리스트에서 순서만 바꾸는 간단 버전 (참고용)
st.markdown("---")
st.subheader("단일 리스트 순서만 드래그해서 바꾸기 (참고용)")

if "simple_icons" not in st.session_state:
    st.session_state.simple_icons = default_icons.copy()

simple_sorted = sort_items(
    st.session_state.simple_icons,
    direction="horizontal",  # 세로로 보고 싶으면 "vertical"
    key="simple_icon_sorter",
)

st.session_state.simple_icons = simple_sorted

st.write("현재 순서:")
for i, icon in enumerate(simple_sorted, start=1):
    st.write(f"{i}. {icon}")
