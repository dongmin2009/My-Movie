import requests
import streamlit as st

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# ============================================================
# 1. 페이지 기본 설정
# ============================================================

st.set_page_config(
    page_title="박스오피스 조회",
    page_icon="🎬",
    layout="wide",
)


# ============================================================
# 2. 한국 시간 기준 날짜 계산
# ============================================================

# Streamlit Cloud 서버의 시간이 한국 시간이 아닐 수 있으므로
# 반드시 한국 시간(Asia/Seoul)을 기준으로 오늘과 어제를 계산합니다.
KST = ZoneInfo("Asia/Seoul")

now_kst = datetime.now(KST)

today_kst = now_kst.date()

# 사용자가 선택할 수 있는 가장 늦은 날짜는 '어제'입니다.
max_date = today_kst - timedelta(days=1)


# ============================================================
# 3. 숫자 변환 함수
# ============================================================

def to_int(value):
    """
    KOBIS API에서는 숫자도 문자열로 옵니다.

    예:
        "12345" -> 12345

    숫자로 변환할 수 없는 값이 들어오면 0을 사용합니다.
    """

    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


# ============================================================
# 4. KOBIS API 호출 함수
# ============================================================

@st.cache_data(ttl=3600)
def get_boxoffice(target_dt):
    """
    선택한 날짜의 KOBIS 일별 박스오피스를 가져옵니다.

    ttl=3600:
        API 결과를 3,600초, 즉 약 1시간 동안 캐시합니다.

    따라서 같은 날짜를 1시간 안에 다시 선택하면
    KOBIS API를 다시 호출하지 않습니다.
    """

    # --------------------------------------------------------
    # Secrets에서 KOBIS 인증키 가져오기
    # --------------------------------------------------------
    #
    # 실제 인증키는 코드에 절대 넣지 않습니다.
    # Streamlit Cloud의 Secrets에 KOBIS_KEY를 등록합니다.
    #

    try:
        api_key = st.secrets["KOBIS_KEY"]

    except KeyError:
        return {
            "success": False,
            "empty": False,
            "error": (
                "KOBIS_KEY를 찾을 수 없습니다.\n\n"
                "Streamlit Cloud의 앱 설정에서 Secrets를 열고 "
                "`KOBIS_KEY`라는 이름으로 인증키가 등록되어 있는지 "
                "확인하세요."
            ),
            "movies": [],
        }

    # --------------------------------------------------------
    # KOBIS 일별 박스오피스 API 주소
    # --------------------------------------------------------

    url = (
        "https://www.kobis.or.kr/"
        "kobisopenapi/webservice/rest/"
        "boxoffice/searchDailyBoxOfficeList.json"
    )

    # API에 전달할 값
    params = {
        "key": api_key,
        "targetDt": target_dt,
    }

    # --------------------------------------------------------
    # API 요청
    # --------------------------------------------------------

    try:
        response = requests.get(
            url,
            params=params,
            timeout=10,
        )

    except requests.exceptions.Timeout:
        return {
            "success": False,
            "empty": False,
            "error": (
                "KOBIS API 응답 시간이 초과되었습니다.\n\n"
                "잠시 후 다시 시도하거나 KOBIS API 서버 상태를 "
                "확인하세요."
            ),
            "movies": [],
        }

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "empty": False,
            "error": (
                "KOBIS API에 연결하지 못했습니다.\n\n"
                "인터넷 연결이나 KOBIS API 서버 상태를 확인하세요.\n\n"
                f"상세 오류: {e}"
            ),
            "movies": [],
        }

    # --------------------------------------------------------
    # HTTP 상태 코드 확인
    # --------------------------------------------------------

    if response.status_code != 200:
        return {
            "success": False,
            "empty": False,
            "error": (
                "KOBIS API 요청에 실패했습니다.\n\n"
                f"HTTP 상태 코드: {response.status_code}\n\n"
                "KOBIS API 서버 상태 또는 네트워크 연결을 "
                "확인하세요."
            ),
            "movies": [],
        }

    # --------------------------------------------------------
    # JSON 응답 읽기
    # --------------------------------------------------------

    try:
        data = response.json()

    except ValueError:
        return {
            "success": False,
            "empty": False,
            "error": (
                "KOBIS API에서 올바른 JSON 응답을 받지 못했습니다.\n\n"
                "KOBIS API 서버의 응답 상태를 확인하세요."
            ),
            "movies": [],
        }

    # ========================================================
    # 5. faultInfo 확인
    # ========================================================

    # KOBIS는 인증키가 잘못되어도 HTTP 200을 반환할 수 있습니다.
    # 따라서 HTTP 상태 코드뿐 아니라 faultInfo도 확인합니다.

    if "faultInfo" in data:

        fault_info = data["faultInfo"]

        error_code = fault_info.get(
            "errorCode",
            "알 수 없음",
        )

        error_message = fault_info.get(
            "message",
            "알 수 없는 오류입니다.",
        )

        return {
            "success": False,
            "empty": False,
            "error": (
                "KOBIS API에서 오류를 반환했습니다.\n\n"
                f"오류 코드: {error_code}\n"
                f"오류 내용: {error_message}\n\n"
                "KOBIS_KEY가 정확한지, 인증키가 유효한지, "
                "KOBIS Open API 사용 신청이 정상인지 확인하세요."
            ),
            "movies": [],
        }

    # ========================================================
    # 6. boxOfficeResult 확인
    # ========================================================

    boxoffice_result = data.get("boxOfficeResult")

    if not boxoffice_result:
        return {
            "success": False,
            "empty": False,
            "error": (
                "KOBIS 응답에 boxOfficeResult가 없습니다.\n\n"
                "KOBIS API의 응답 형식이나 서버 상태를 확인하세요."
            ),
            "movies": [],
        }

    # ========================================================
    # 7. 영화 목록 확인
    # ========================================================

    movie_list = boxoffice_result.get(
        "dailyBoxOfficeList",
        [],
    )

    # 영화 목록이 비어 있는 경우
    if not movie_list:
        return {
            "success": False,
            "empty": True,
            "error": "",
            "movies": [],
        }

    # ========================================================
    # 8. 필요한 데이터를 가져오고 숫자로 변환
    # ========================================================

    movies = []

    for movie in movie_list:

        movies.append(
            {
                # 순위: 문자열 -> 숫자
                "rank": to_int(movie.get("rank")),

                # 전날 대비 순위 증감: 문자열 -> 숫자
                "rankInten": to_int(movie.get("rankInten")),

                # 영화명
                "movieNm": movie.get("movieNm", ""),

                # 개봉일
                "openDt": movie.get("openDt", ""),

                # 그날 관객수: 문자열 -> 숫자
                "audiCnt": to_int(movie.get("audiCnt")),

                # 누적 관객수: 문자열 -> 숫자
                "audiAcc": to_int(movie.get("audiAcc")),

                # 스크린수: 문자열 -> 숫자
                "scrnCnt": to_int(movie.get("scrnCnt")),
            }
        )

    # 순위를 숫자 기준으로 정렬합니다.
    movies.sort(
        key=lambda movie: movie["rank"]
    )

    return {
        "success": True,
        "empty": False,
        "error": "",
        "movies": movies,
    }


# ============================================================
# 9. 제목과 날짜 선택
# ============================================================

st.title("🎬 박스오피스 조회")

st.caption(
    "한국 시간 기준 · 오늘은 아직 집계 전이므로 어제까지 조회할 수 있습니다."
)


# ------------------------------------------------------------
# 날짜 선택 달력
# ------------------------------------------------------------

selected_date = st.date_input(
    "조회 날짜",
    value=max_date,
    min_value=None,
    max_value=max_date,
)


# 선택한 날짜를 KOBIS API 형식인 YYYYMMDD로 변환합니다.
target_dt = selected_date.strftime("%Y%m%d")

display_date = selected_date.strftime(
    "%Y년 %m월 %d일"
)


# ============================================================
# 10. 선택한 날짜의 데이터 가져오기
# ============================================================

result = get_boxoffice(target_dt)


# ============================================================
# 11. 영화 목록이 없는 경우
# ============================================================

if result["empty"]:

    st.warning(
        f"📅 {display_date} 박스오피스 데이터가 없습니다."
    )

    st.info(
        "그날은 아직 집계 전입니다.\n\n"
        "다른 날짜를 선택해 보세요."
    )

    st.stop()


# ============================================================
# 12. API 오류가 발생한 경우
# ============================================================

if not result["success"]:

    st.error(
        "박스오피스 데이터를 가져오지 못했습니다."
    )

    st.warning(
        result["error"]
    )

    st.info(
        "확인할 항목\n\n"
        "1. Streamlit Cloud → 앱 설정 → Secrets에서 "
        "`KOBIS_KEY`가 등록되어 있는지 확인하세요.\n\n"
        "2. KOBIS 인증키가 정확하고 유효한지 확인하세요.\n\n"
        "3. KOBIS Open API 서버가 정상적으로 응답하는지 "
        "확인하세요.\n\n"
        "4. 선택한 날짜의 박스오피스 데이터가 존재하는지 "
        "확인하세요."
    )

    st.stop()


movies = result["movies"]


# ============================================================
# 13. 1위 영화
# ============================================================

first_movie = movies[0]

# 누적관객이 100만 명을 넘었으면 트로피를 붙입니다.
first_trophy = (
    " 🏆"
    if first_movie["audiAcc"] > 1_000_000
    else ""
)

st.header(
    f"🥇 1위 · {first_movie['movieNm']}{first_trophy}"
)


# ============================================================
# 14. 1위 영화의 지표 카드 3개
# ============================================================

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


# ============================================================
# 15. 관객수 상위 5편 그래프
# ============================================================

st.subheader("📊 관객수 상위 5편")


# 관객수가 많은 순서로 정렬합니다.
top5 = sorted(
    movies,
    key=lambda movie: movie["audiCnt"],
    reverse=True,
)[:5]


# Streamlit 그래프용 데이터를 만듭니다.
chart_data = {
    movie["movieNm"]: movie["audiCnt"]
    for movie in top5
}


st.bar_chart(chart_data)


st.divider()


# ============================================================
# 16. 전체 박스오피스 표
# ============================================================

st.subheader("📋 전체 순위")


table_data = []

for movie in movies:

    # --------------------------------------------------------
    # 순위 증감 표시
    # --------------------------------------------------------
    #
    # rankInten > 0 : 순위가 올랐음 → 빨간 위 화살표
    # rankInten < 0 : 순위가 내려갔음 → 파란 아래 화살표
    # rankInten == 0: 변화 없음
    #

    rank_inten = movie["rankInten"]

    if rank_inten > 0:
        rank_change = f"🔺 {rank_inten}"

    elif rank_inten < 0:
        # 음수 값을 그대로 표시하지 않고
        # 내려간 칸에서는 절댓값을 보여줍니다.
        rank_change = f"🔻 {abs(rank_inten)}"

    else:
        rank_change = "—"

    # --------------------------------------------------------
    # 누적관객 100만 명 초과 여부 확인
    # --------------------------------------------------------

    trophy = (
        " 🏆"
        if movie["audiAcc"] > 1_000_000
        else ""
    )

    # 표에 들어갈 데이터를 만듭니다.
    table_data.append(
        {
            "순위": movie["rank"],
            "증감": rank_change,
            "영화명": f"{movie['movieNm']}{trophy}",
            "개봉일": movie["openDt"],
            "관객수": movie["audiCnt"],
            "누적관객": movie["audiAcc"],
            "스크린수": movie["scrnCnt"],
        }
    )


# ============================================================
# 17. 표 출력
# ============================================================

st.dataframe(
    table_data,
    use_container_width=True,
    hide_index=True,

    column_config={
        # 순위는 실제 숫자입니다.
        "순위": st.column_config.NumberColumn(
            "순위",
            format="%d",
        ),

        # 증감은 화살표 이모지를 포함한 문자열입니다.
        "증감": st.column_config.TextColumn(
            "전일 대비",
        ),

        "영화명": st.column_config.TextColumn(
            "영화명",
        ),

        "개봉일": st.column_config.TextColumn(
            "개봉일",
        ),

        # 아래 숫자들은 모두 실제 int 타입입니다.
        # 따라서 표에서 숫자 기준으로 정렬할 수 있습니다.
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


# ============================================================
# 18. 안내 문구
# ============================================================

st.caption(
    "🔺 순위 상승 · 🔻 순위 하락 · "
    "🏆 누적관객 100만 명 초과"
)

st.caption(
    "※ 같은 날짜의 KOBIS API 결과는 약 1시간 동안 캐시됩니다."
)
