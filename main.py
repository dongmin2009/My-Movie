import requests
import streamlit as st
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# ---------------------------------------------------------
# 1. 기본 페이지 설정
# ---------------------------------------------------------
st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide",
)


# ---------------------------------------------------------
# 2. 한국 시간 기준으로 '어제' 날짜 계산
# ---------------------------------------------------------
# 배포 서버가 어느 나라 시간으로 설정되어 있어도
# 한국 시간(KST)을 기준으로 날짜를 계산합니다.
kst = ZoneInfo("Asia/Seoul")
today_kst = datetime.now(kst).date()
yesterday_kst = today_kst - timedelta(days=1)

# KOBIS API가 요구하는 YYYYMMDD 형식으로 변환합니다.
target_date = yesterday_kst.strftime("%Y%m%d")
display_date = yesterday_kst.strftime("%Y년 %m월 %d일")


# ---------------------------------------------------------
# 3. KOBIS API 호출 함수
# ---------------------------------------------------------
@st.cache_data(ttl=3600)
def get_boxoffice(target_dt):
    """
    KOBIS 일별 박스오피스 API를 호출합니다.

    st.cache_data(ttl=3600)을 사용했기 때문에
    같은 날짜를 1시간 안에 다시 조회하면 API를 다시 호출하지 않습니다.
    """

    # Streamlit Cloud의 Secrets에서 인증키를 가져옵니다.
    # 실제 인증키를 코드에 직접 적으면 안 됩니다.
    api_key = st.secrets.get("KOBIS_KEY")

    if not api_key:
        return {
            "ok": False,
            "message": (
                "KOBIS_KEY를 찾을 수 없습니다. "
                "Streamlit Cloud의 앱 설정에서 Secrets에 "
                "`KOBIS_KEY`가 정확히 등록되어 있는지 확인하세요."
            ),
            "movies": [],
        }

    url = (
        "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
        "boxoffice/searchDailyBoxOfficeList.json"
    )

    params = {
        "key": api_key,
        "targetDt": target_dt,
    }

    try:
        # KOBIS 서버에 API 요청을 보냅니다.
        response = requests.get(
            url,
            params=params,
            timeout=10,
        )

        # HTTP 상태 코드가 200인지 확인합니다.
        if response.status_code != 200:
            return {
                "ok": False,
                "message": (
                    f"KOBIS API 요청이 실패했습니다. "
                    f"HTTP 상태 코드: {response.status_code}"
                ),
                "movies": [],
            }

        # JSON 응답을 읽습니다.
        data = response.json()

    except requests.exceptions.Timeout:
        return {
            "ok": False,
            "message": (
                "KOBIS API 응답 시간이 초과되었습니다. "
                "잠시 후 다시 시도하거나 KOBIS API 서버 상태를 확인하세요."
            ),
            "movies": [],
        }

    except requests.exceptions.RequestException as e:
        return {
            "ok": False,
            "message": (
                "KOBIS API에 연결하지 못했습니다. "
                "인터넷 연결이나 KOBIS API 서버 상태를 확인하세요."
                f"\n\n오류 내용: {e}"
            ),
            "movies": [],
        }

    except ValueError:
        return {
            "ok": False,
            "message": (
                "KOBIS API가 올바른 JSON 응답을 보내지 않았습니다. "
                "KOBIS API 응답 상태를 확인하세요."
            ),
            "movies": [],
        }

    # -----------------------------------------------------
    # 4. KOBIS의 faultInfo 확인
    # -----------------------------------------------------
    # KOBIS는 인증키가 틀려도 HTTP 200을 반환할 수 있습니다.
    # 따라서 HTTP 상태 코드만 보고 성공이라고 판단하면 안 됩니다.
    if "faultInfo" in data:
        fault_info = data["faultInfo"]

        fault_code = fault_info.get("errorCode", "알 수 없음")
        fault_message = fault_info.get("message", "알 수 없는 오류")

        return {
            "ok": False,
            "message": (
                "KOBIS API에서 오류를 반환했습니다.\n\n"
                f"오류 코드: {fault_code}\n"
                f"오류 내용: {fault_message}\n\n"
                "KOBIS_KEY가 올바른지, API 사용 신청과 인증키 상태가 "
                "정상인지 확인하세요."
            ),
            "movies": [],
        }

    # -----------------------------------------------------
    # 5. 영화 목록 가져오기
    # -----------------------------------------------------
    boxoffice_result = data.get("boxOfficeResult", {})
    movie_list = boxoffice_result.get("dailyBoxOfficeList", [])

    # 영화 목록이 비어 있는 경우도 사용자에게 안내합니다.
    if not movie_list:
        return {
            "ok": False,
            "message": (
                f"{target_dt} 날짜의 박스오피스 영화 목록이 없습니다.\n\n"
                "조회 날짜가 실제로 집계 가능한 날짜인지, "
                "KOBIS API 응답에 문제가 없는지 확인하세요."
            ),
            "movies": [],
        }

    # -----------------------------------------------------
    # 6. 문자열로 온 숫자를 실제 숫자로 변환
    # -----------------------------------------------------
    movies = []

    for movie in movie_list:
        movies.append(
            {
                "rank": int(movie.get("rank", 0)),
                "movieNm": movie.get("movieNm", ""),
                "openDt": movie.get("openDt", ""),
                "audiCnt": int(movie.get("audiCnt", 0)),
                "audiAcc": int(movie.get("audiAcc", 0)),
                "scrnCnt": int(movie.get("scrnCnt", 0)),
            }
        )

    # 순위 숫자를 기준으로 정렬합니다.
    movies.sort(key=lambda x: x["rank"])

    return {
        "ok": True,
        "message": "",
        "movies": movies,
    }


# ---------------------------------------------------------
# 7. API 데이터 가져오기
# ---------------------------------------------------------
result = get_boxoffice(target_date)


# ---------------------------------------------------------
# 8. 제목
# ---------------------------------------------------------
st.title("🎬 어제의 박스오피스")
st.caption(
    f"KOBIS 일별 박스오피스 · 한국 시간 기준 {display_date}"
)


# ---------------------------------------------------------
# 9. API 오류가 있으면 안내 메시지 표시
# ---------------------------------------------------------
if not result["ok"]:
    st.error("박스오피스 데이터를 가져오지 못했습니다.")

    st.warning(result["message"])

    st.info(
        "확인할 항목: "
        "① Streamlit Secrets의 KOBIS_KEY "
        "② KOBIS 인증키 유효성 "
        "③ KOBIS API 서버 상태 "
        "④ 해당 날짜의 박스오피스 데이터 존재 여부"
    )

    st.stop()


movies = result["movies"]


# ---------------------------------------------------------
# 10. 1위 영화 정보
# ---------------------------------------------------------
first_movie = movies[0]

st.header(f"🥇 1위 · {first_movie['movieNm']}")


# 숫자에 천 단위 쉼표를 붙이는 함수
def comma(number):
    return f"{number:,}"


# ---------------------------------------------------------
# 11. 1위 영화의 지표 카드 3개
# ---------------------------------------------------------
col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        label="어제 관객수",
        value=f"{comma(first_movie['audiCnt'])}명",
    )

with col2:
    st.metric(
        label="누적 관객수",
        value=f"{comma(first_movie['audiAcc'])}명",
    )

with col3:
    st.metric(
        label="스크린수",
        value=f"{comma(first_movie['scrnCnt'])}개",
    )


st.divider()


# ---------------------------------------------------------
# 12. 관객수 상위 5편 막대그래프
# ---------------------------------------------------------
st.subheader("📊 관객수 상위 5편")

# 관객수가 많은 순서로 정렬합니다.
top5 = sorted(
    movies,
    key=lambda x: x["audiCnt"],
    reverse=True,
)[:5]

# Streamlit의 bar_chart에 넣기 좋은 형태로 만듭니다.
chart_data = {
    movie["movieNm"]: movie["audiCnt"]
    for movie in top5
}

st.bar_chart(chart_data)


# ---------------------------------------------------------
# 13. 전체 박스오피스 표
# ---------------------------------------------------------
st.subheader("📋 전체 순위")

# 화면에 보여줄 표 데이터를 만듭니다.
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

st.dataframe(
    table_data,
    use_container_width=True,
    hide_index=True,
    column_config={
        "순위": st.column_config.NumberColumn(
            "순위",
            format="%d",
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


# ---------------------------------------------------------
# 14. 캐시 안내
# ---------------------------------------------------------
st.caption(
    "※ 같은 조회 날짜의 KOBIS API 결과는 약 1시간 동안 캐시됩니다."
)
```

```text
streamlit
requests
```

이대로 프로젝트 루트에 **`main.py`**와 **`requirements.txt`**를 두고 Streamlit Cloud에서 `main.py`를 앱 파일로 지정하면 됩니다. `zoneinfo`는 Python 표준 라이브러리라 별도 설치가 필요 없습니다.

원하시면 제가 이어서 **Streamlit Cloud의 Secrets에 `KOBIS_KEY`를 넣는 방법까지 초보자 기준으로** 정리해 드릴게요.
