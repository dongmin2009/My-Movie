import requests
import streamlit as st

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# ============================================================
# 1. 페이지 기본 설정
# ============================================================

st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide",
)


# ============================================================
# 2. 한국 시간 기준으로 '어제' 날짜 계산
# ============================================================

# Streamlit Cloud 서버의 시간이 한국 시간이 아닐 수 있으므로
# 반드시 한국 시간(Asia/Seoul)을 기준으로 날짜를 계산합니다.
KST = ZoneInfo("Asia/Seoul")

now_kst = datetime.now(KST)

# 한국 시간 기준 오늘에서 하루를 빼면 '어제'입니다.
yesterday = now_kst.date() - timedelta(days=1)

# KOBIS API가 요구하는 날짜 형식: YYYYMMDD
target_dt = yesterday.strftime("%Y%m%d")

# 화면에 표시할 날짜
display_date = yesterday.strftime("%Y년 %m월 %d일")


# ============================================================
# 3. 숫자 변환 함수
# ============================================================

def to_int(value):
    """
    KOBIS API의 숫자 값은 문자열로 옵니다.

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
    KOBIS 일별 박스오피스 API를 호출합니다.

    ttl=3600:
        API 결과를 3,600초, 즉 약 1시간 동안 기억합니다.

    따라서 같은 target_dt를 다시 요청하면
    캐시가 살아 있는 동안 KOBIS API를 다시 호출하지 않습니다.
    """

    # --------------------------------------------------------
    # Secrets에서 KOBIS 인증키 가져오기
    # --------------------------------------------------------
    #
    # 실제 인증키는 이 코드에 넣지 않습니다.
    # Streamlit Cloud의 Secrets에 KOBIS_KEY를 등록해야 합니다.
    #

    try:
        api_key = st.secrets["KOBIS_KEY"]

    except KeyError:
        return {
            "success": False,
            "error": (
                "KOBIS_KEY를 찾을 수 없습니다.\n\n"
                "Streamlit Cloud의 앱 설정에서 Secrets를 열고 "
                "`KOBIS_KEY`라는 이름으로 인증키가 등록되어 있는지 "
                "확인하세요."
            ),
            "movies": [],
        }

    # --------------------------------------------------------
    # KOBIS 공식 일별 박스오피스 API 주소
    # --------------------------------------------------------

    url = (
        "https://www.kobis.or.kr/"
        "kobisopenapi/webservice/rest/"
        "boxoffice/searchDailyBoxOfficeList.json"
    )

    # API에 보낼 요청값
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
            "error": (
                "KOBIS API에서 올바른 JSON 응답을 받지 못했습니다.\n\n"
                "KOBIS API 서버의 응답 상태를 확인하세요."
            ),
            "movies": [],
        }

    # ========================================================
    # 5. faultInfo 확인
    # ========================================================

    # 중요:
    #
    # KOBIS는 인증키가 틀린 경우에도 HTTP 상태 코드가 200일 수
    # 있습니다.
    #
    # 따라서 response.status_code만 확인해서는 안 되고
    # JSON 안에 faultInfo가 있는지도 확인해야 합니다.

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

    # 영화 목록이 비어 있으면 빈 화면을 보여주지 않고
    # 사용자가 확인해야 할 내용을 알려줍니다.
    if not movie_list:
        return {
            "success": False,
            "error": (
                f"{target_dt} 날짜의 박스오피스 영화 목록이 없습니다.\n\n"
                "다음 사항을 확인하세요.\n\n"
                "• 해당 날짜의 박스오피스가 실제로 집계되었는지 확인\n"
                "• KOBIS API 서버 상태 확인\n"
                "• KOBIS API 응답 내용 확인"
            ),
            "movies": [],
        }

    # ========================================================
    # 8. 필요한 데이터만 골라서 숫자로 변환
    # ========================================================

    movies = []

    for movie in movie_list:

        movies.append(
            {
                # 순위: 문자열 -> 숫자
                "rank": to_int(movie.get("rank")),

                # 영화명: 문자열 그대로 사용
                "movieNm": movie.get("movieNm", ""),

                # 개봉일: 날짜 표시용이므로 문자열 그대로 사용
                "openDt": movie.get("openDt", ""),

                # 관객수: 문자열 -> 숫자
                "audiCnt": to_int(movie.get("audiCnt")),

                # 누적관객: 문자열 -> 숫자
                "audiAcc": to_int(movie.get("audiAcc")),

                # 스크린수: 문자열 -> 숫자
                "scrnCnt": to_int(movie.get("scrnCnt")),
            }
        )

    # 순위가 낮은 영화부터 정렬합니다.
    # 예: 1위 -> 2위 -> 3위 ...
    movies.sort(key=lambda movie: movie["rank"])

    return {
        "success": True,
        "error": "",
        "movies": movies,
    }


# ============================================================
# 9. KOBIS 데이터 가져오기
# ============================================================

result = get_boxoffice(target_dt)


# ============================================================
# 10. 페이지 제목
# ============================================================

st.title("🎬 어제의 박스오피스")

st.caption(
    f"KOBIS 일별 박스오피스 · 한국 시간 기준 {display_date}"
)


# ============================================================
# 11. API 오류 처리
# ============================================================

if not result["success"]:

    # 사용자에게 오류가 발생했다는 것을 먼저 알려줍니다.
    st.error("박스오피스 데이터를 가져오지 못했습니다.")

    # 구체적인 오류 내용을 보여줍니다.
    st.warning(result["error"])

    # 사용자가 확인할 곳을 한 번 더 정리합니다.
    st.info(
        "확인할 항목\n\n"
        "1. Streamlit Cloud → 앱 설정 → Secrets에서 "
        "`KOBIS_KEY`가 등록되어 있는지 확인하세요.\n\n"
        "2. KOBIS 인증키가 정확하고 유효한지 확인하세요.\n\n"
        "3. KOBIS Open API 서버가 정상적으로 응답하는지 확인하세요.\n\n"
        "4. 해당 날짜의 일별 박스오피스 데이터가 존재하는지 "
        "확인하세요."
    )

    # 오류가 있을 때는 아래의 그래프와 표를 만들지 않습니다.
    st.stop()


# 정상적으로 데이터를 받은 경우
movies = result["movies"]


# ============================================================
# 12. 1위 영화 정보
# ============================================================

first_movie = movies[0]

st.header(
    f"🥇 1위 · {first_movie['movieNm']}"
)


# ============================================================
# 13. 1위 영화 지표 카드 3개
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
# 14. 관객수 상위 5편 막대그래프
# ============================================================

st.subheader("📊 관객수 상위 5편")


# audiCnt가 큰 영화부터 정렬한 다음
# 앞에서 5개만 가져옵니다.
top5 = sorted(
    movies,
    key=lambda movie: movie["audiCnt"],
    reverse=True,
)[:5]


# Streamlit 막대그래프에 사용할 데이터를 만듭니다.
#
# 영화명 -> 관객수
#
# 관객수는 앞에서 이미 int로 변환했기 때문에
# 그래프에서도 숫자로 정상 처리됩니다.
chart_data = {
    movie["movieNm"]: movie["audiCnt"]
    for movie in top5
}


st.bar_chart(chart_data)


st.divider()


# ============================================================
# 15. 전체 박스오피스 표
# ============================================================

st.subheader("📋 전체 순위")


# 표에 표시할 데이터를 준비합니다.
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


# 표 출력
st.dataframe(
    table_data,
    use_container_width=True,
    hide_index=True,

    # 각 열의 데이터 타입과 표시 형식을 지정합니다.
    # 실제 데이터는 숫자이므로 정렬도 숫자 기준으로 됩니다.
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


# ============================================================
# 16. 캐시 안내
# ============================================================

st.caption(
    "※ 같은 날짜의 KOBIS API 결과는 약 1시간 동안 캐시됩니다."
)
