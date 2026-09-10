import requests
import streamlit as st
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# =========================================================
# 1. Streamlit 화면 기본 설정
# =========================================================

st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide",
)


# =========================================================
# 2. 한국 시간 기준으로 '어제' 날짜 계산
# =========================================================

# 배포 서버가 미국이나 다른 나라 시간으로 설정되어 있어도
# ZoneInfo("Asia/Seoul")을 사용하면 한국 시간을 기준으로 계산할 수 있습니다.
KST = ZoneInfo("Asia/Seoul")

now_kst = datetime.now(KST)

# 오늘 날짜에서 하루를 빼서 '어제'를 구합니다.
yesterday = now_kst.date() - timedelta(days=1)

# KOBIS API가 요구하는 날짜 형식: YYYYMMDD
target_dt = yesterday.strftime("%Y%m%d")

# 화면에 보여줄 날짜 형식
display_date = yesterday.strftime("%Y년 %m월 %d일")


# =========================================================
# 3. KOBIS API 호출 함수
# =========================================================

@st.cache_data(ttl=3600)
def get_boxoffice(target_dt):
    """
    KOBIS 일별 박스오피스 데이터를 가져오는 함수입니다.

    ttl=3600은 캐시를 3,600초(약 1시간) 동안 유지한다는 뜻입니다.
    따라서 같은 날짜를 다시 조회하면 1시간 동안 API를 다시 호출하지 않습니다.
    """

    # -----------------------------------------------------
    # Streamlit Secrets에서 인증키를 가져옵니다.
    #
    # 실제 인증키는 코드에 적지 않습니다.
    # Streamlit Cloud의 Secrets에 KOBIS_KEY를 등록해야 합니다.
    # -----------------------------------------------------

    try:
        api_key = st.secrets["KOBIS_KEY"]
    except KeyError:
        return {
            "success": False,
            "error": (
                "KOBIS_KEY를 찾을 수 없습니다.\n\n"
                "Streamlit Cloud의 앱 설정에서 Secrets를 열고 "
                "`KOBIS_KEY`라는 이름으로 인증키가 등록되어 있는지 확인하세요."
            ),
            "movies": [],
        }

    # KOBIS 일별 박스오피스 API 주소입니다.
    url = (
        "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
        "boxoffice/searchDailyBoxOfficeList.json"
    )

    # API에 전달할 값입니다.
    params = {
        "key": api_key,
        "targetDt": target_dt,
    }

    # -----------------------------------------------------
    # API 요청
    # -----------------------------------------------------

    try:
        response = requests.get(
            url,
            params=params,
            timeout=10,
        )

    except requests.exceptions.Timeout:
        return {
            "success": False,
            "error": (
                "KOBIS API 응답 시간이 초과되었습니다.\n\n"
                "잠시 후 다시 시도하거나 KOBIS API 서버 상태를 확인하세요."
            ),
            "movies": [],
        }

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": (
                "KOBIS API에 연결하지 못했습니다.\n\n"
                "인터넷 연결이나 KOBIS API 서버 상태를 확인하세요.\n\n"
                f"상세 오류: {e}"
            ),
            "movies": [],
        }

    # -----------------------------------------------------
    # HTTP 상태 코드 확인
    # -----------------------------------------------------

    if response.status_code != 200:
        return {
            "success": False,
            "error": (
                "KOBIS API 요청에 실패했습니다.\n\n"
                f"HTTP 상태 코드: {response.status_code}\n\n"
                "KOBIS API 서버 상태나 네트워크 연결을 확인하세요."
            ),
            "movies": [],
        }

    # -----------------------------------------------------
    # JSON 응답으로 변환
    # -----------------------------------------------------

    try:
        data = response.json()
    except ValueError:
        return {
            "success": False,
            "error": (
                "KOBIS API에서 올바른 JSON 데이터를 받지 못했습니다.\n\n"
                "KOBIS API 서버의 응답 상태를 확인하세요."
            ),
            "movies": [],
        }

    # =====================================================
    # 4. faultInfo 확인
    # =====================================================

    # 중요:
    # KOBIS는 인증키가 잘못되어도 HTTP 상태 코드가 200일 수 있습니다.
    # 그래서 status_code만 확인하지 않고 faultInfo도 확인합니다.

    if "faultInfo" in data:
        fault_info = data["faultInfo"]

        error_code = fault_info.get("errorCode", "알 수 없음")
        error_message = fault_info.get(
            "message",
            "알 수 없는 오류입니다.",
        )

        return {
            "success": False,
            "error": (
                "KOBIS API에서 오류를 반환했습니다.\n\n"
                f"오류 코드: {error_code}\n"
                f"오류 내용: {error_message}\n\n"
                "KOBIS_KEY가 정확한지, 인증키가 유효한지, "
                "KOBIS Open API 사용 신청이 정상인지 확인하세요."
            ),
            "movies": [],
        }

    # =====================================================
    # 5. 영화 목록 가져오기
    # =====================================================

    boxoffice_result = data.get("boxOfficeResult")

    if not boxoffice_result:
        return {
            "success": False,
            "error": (
                "KOBIS 응답에 boxOfficeResult가 없습니다.\n\n"
                "KOBIS API의 응답 형식과 서버 상태를 확인하세요."
            ),
            "movies": [],
        }

    movie_list = boxoffice_result.get("dailyBoxOfficeList", [])

    # 영화 목록이 비어 있으면 안내합니다.
    if not movie_list:
        return {
            "success": False,
            "error": (
                f"{target_dt} 날짜의 박스오피스 영화 목록이 없습니다.\n\n"
                "다음 사항을 확인하세요.\n"
                "• 해당 날짜의 박스오피스가 실제로 집계되었는지 확인\n"
                "• KOBIS API 서버 상태 확인\n"
                "• KOBIS API 응답 내용 확인"
            ),
            "movies": [],
        }

    # =====================================================
    # 6. 숫자 문자열을 실제 숫자로 변환
    # =====================================================

    movies = []

    for movie in movie_list:

        # KOBIS API에서는 숫자도 문자열로 전달됩니다.
        # int()를 사용해서 실제 숫자로 변환합니다.
        try:
            rank = int(movie.get("rank", 0))
        except (TypeError, ValueError):
            rank = 0

        try:
            audi_cnt = int(movie.get("audiCnt", 0))
        except (TypeError, ValueError):
            audi_cnt = 0

        try:
            audi_acc = int(movie.get("audiAcc", 0))
        except (TypeError, ValueError):
            audi_acc = 0

        try:
            scrn_cnt = int(movie.get("scrnCnt", 0))
        except (TypeError, ValueError):
            scrn_cnt = 0

        movies.append(
            {
                "rank": rank,
                "movieNm": movie.get("movieNm", ""),
                "openDt": movie.get("openDt", ""),
                "audiCnt": audi_cnt,
                "audiAcc": audi_acc,
                "scrnCnt": scrn_cnt,
            }
        )

    # 순위를 숫자 기준으로 정렬합니다.
    movies.sort(key=lambda movie: movie["rank"])

    return {
        "success": True,
        "error": "",
        "movies": movies,
    }


# =========================================================
# 7. 박스오피스 데이터 가져오기
# =========================================================

result = get_boxoffice(target_dt)


# =========================================================
# 8. 제목
# =========================================================

st.title("🎬 어제의 박스오피스")

st.caption(
    f"KOBIS 일별 박스오피스 · 한국 시간 기준 {display_date}"
)


# =========================================================
# 9. API 오류가 발생한 경우
# =========================================================

if not result["success"]:

    st.error("박스오피스 데이터를 가져오지 못했습니다.")

    # 사용자에게 오류 내용을 한국어로 보여줍니다.
    st.warning(result["error"])

    st.info(
        "확인할 항목\n\n"
        "1. Streamlit Cloud → 앱 → Settings → Secrets에서 "
        "`KOBIS_KEY`가 등록되어 있는지 확인하세요.\n\n"
        "2. KOBIS 인증키가 정확하고 유효한지 확인하세요.\n\n"
        "3. KOBIS Open API 서버가 정상적으로 응답하는지 확인하세요.\n\n"
        "4. 해당 날짜의 일별 박스오피스 데이터가 존재하는지 확인하세요."
    )

    # 오류 상태에서는 아래의 표와 그래프를 만들지 않습니다.
    st.stop()


# 정상적으로 데이터를 가져온 경우
movies = result["movies"]


# =========================================================
# 10. 1위 영화
# =========================================================

first_movie = movies[0]

st.header(
    f"🥇 1위 · {first_movie['movieNm']}"
)


# =========================================================
# 11. 1위 영화의 지표 카드 3개
# =========================================================

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        label="어제 관객수",
        value=f"{first_movie['audiCnt']:,}명",
    )

with col2:
    st.metric(
        label="누적 관객수",
        value=f"{first_movie['audiAcc']:,}명",
    )

with col3:
    st.metric(
        label="스크린수",
        value=f"{first_movie['scrnCnt']:,}개",
    )


st.divider()


# =========================================================
# 12. 관객수 상위 5편
# =========================================================

st.subheader("📊 관객수 상위 5편")

# 관객수(audiCnt)를 기준으로 큰 순서대로 정렬합니다.
top5 = sorted(
    movies,
    key=lambda movie: movie["audiCnt"],
    reverse=True,
)[:5]


# ---------------------------------------------------------
# Streamlit 그래프용 데이터 만들기
# ---------------------------------------------------------

# 딕셔너리의
#   영화명 → 관객수
# 형태로 만들어 st.bar_chart()에 전달합니다.
chart_data = {
    movie["movieNm"]: movie["audiCnt"]
    for movie in top5
}

st.bar_chart(chart_data)


st.divider()


# =========================================================
# 13. 전체 박스오피스 표
# =========================================================

st.subheader("📋 전체 순위")


# 표에 표시할 데이터를 만듭니다.
table_data = []

for movie in movies:
    table_data.append(
        {
            "순위": movie["rank"],
            "영화명": movie["movieNm"],
            "개봉일": movie["openDt"],
            "관객수": movie["audiCnt"],
            "누적관객": movie["audiAcc"],
            "스크린수": movie["scrnCnt"],
        }
    )


# ---------------------------------------------------------
# 표 출력
# ---------------------------------------------------------

st.dataframe(
    table_data,
    use_container_width=True,
    hide_index=True,
    column_config={
        "순위": st.column_config.NumberColumn(
            "순위",
            format="%d",
        ),
        "영화명": st.column_config.TextColumn(
            "영화명",
        ),
        "개봉일": st.column_config.TextColumn(
            "개봉일",
        ),
        "관객수": st.column_config.NumberColumn(
            "관객수",
            format="%d명",
        ),
        "누적관객": st.column_config.NumberColumn(
            "누적관객",
            format="%d명",
        ),
        "스크린수": st.column_config.NumberColumn(
            "스크린수",
            format="%d개",
        ),
    },
)


# =========================================================
# 14. 캐시 안내
# =========================================================

st.caption(
    "※ 같은 날짜의 KOBIS API 결과는 약 1시간 동안 캐시됩니다."
)
