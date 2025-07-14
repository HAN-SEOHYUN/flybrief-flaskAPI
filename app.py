from flask import Flask, request, jsonify
from datetime import datetime
import requests
import os
from dotenv import load_dotenv
import re

# .env 로드
load_dotenv()

app = Flask(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama3-8b-8192"

def build_prompt(location, start_date, end_date):
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        return None

    if start_dt.month == end_dt.month:
        return f"{start_dt.month}월의 {location} 여행인데, 날씨가 어떤지 알려줘!"
    else:
        return f"{start_date}일부터 {end_date}일까지 {location} 여행이야. 날씨가 어떤지 활기차고 친절하게 알려줘!"

def build_travel_recommendation_prompt(travel_theme):
    current_month = datetime.now().month
    month_names = {
        1: "1월", 2: "2월", 3: "3월", 4: "4월", 5: "5월", 6: "6월",
        7: "7월", 8: "8월", 9: "9월", 10: "10월", 11: "11월", 12: "12월"
    }
    current_month_name = month_names[current_month]
    
    return f"여행 테마: {travel_theme}\n현재 시기: {current_month_name}"

@app.route('/weather-summary', methods=['POST'])
def weather_summary():
    data = request.get_json()
    location = data.get("location")
    start_date = data.get("startDate")
    end_date = data.get("endDate")

    prompt = build_prompt(location, start_date, end_date)
    if not prompt:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a cheerful and energetic travel agent! ☀️✈️ "
                    "When a user provides a travel destination and date range, describe the expected weather during that period using only natural sentences. "
                    "The tone should be friendly and positive, as if you're recommending a great trip. Feel free to use emojis to add a lively mood. "
                    "Also, based on the weather information, suggest what items travelers should pack for their trip. "
                    "Do not use JSON, tables, or bullet points — respond like you're chatting with a traveler! "
                    "Important: You must respond **only in Korean**, except for the city name which should remain in English (e.g., Paris, Tokyo). "
                    "Do not include any English words other than the location name. Keep the response under 9 sentences."
                )
            },
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7
    }

    try:
        response = requests.post(GROQ_API_URL, headers=headers, json=payload)
        response.raise_for_status()

        content = response.json()["choices"][0]["message"]["content"]
        
        # 두 번째 요청: 답변을 정돈된 문장으로 정리
        refinement_payload = {
            "model": GROQ_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "당신은 한국어 텍스트 편집 전문가입니다. "
                        "주어진 날씨 정보를 읽기 쉽고 정돈된 한국어 문장으로 정리해주세요. "
                        "한자, 일본어, 중국어가 포함되어있다면 반드시 제거해주세요. "
                        "문장을 자연스럽게 연결하고, 불필요한 반복을 제거하며, "
                        "전체적으로 일관성 있고 친근한 날씨 안내 글로 만들어주세요. "
                    )
                },
                {"role": "user", "content": f"다음 날씨 정보를 정돈된 문장으로 정리해주세요:\n\n{content}"}
            ],
            "temperature": 0.5
        }
        
        try:
            refinement_response = requests.post(GROQ_API_URL, headers=headers, json=refinement_payload)
            refinement_response.raise_for_status()
            
            final_content = refinement_response.json()["choices"][0]["message"]["content"]
            return jsonify({"message": final_content})
            
        except requests.exceptions.HTTPError as http_err:
            print("🔴 Refinement HTTPError:", refinement_response.text)
            # 정리 실패 시 원본 답변 반환
            return jsonify({"message": content})
        except Exception as e:
            # 정리 실패 시 원본 답변 반환
            return jsonify({"message": content})

    except requests.exceptions.HTTPError as http_err:
        print("🔴 HTTPError:", response.text)
        return jsonify({"error": f"{http_err} - {response.text}"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/travel-recommendations', methods=['POST'])
def travel_recommendations():
    data = request.get_json()
    travel_theme = data.get("travelTheme")

    if not travel_theme:
        return jsonify({"error": "travelTheme is required"}), 400

    prompt = build_travel_recommendation_prompt(travel_theme)

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "사용자가 제공한 여행 테마에 맞는 여행지를 3개 추천해주세요. "
                    "해당 여행지를 방문하기 위한 인근 공항 한글,영문명과 iata code 를 알려주세요. "
                    "반드시 현재 월에 실제로 방문하거나 즐길 수 있는 여행지/축제만 추천해야 합니다. "
                    "현재 월에 맞지 않는 계절이나 시기의 여행지는 절대 추천하지 마세요. "
                    "그리고 지역명을 말할 때는 반드시 iata code가 포함되어야 합니다. 예: 캐나다 퀘백(YQB) 대한민국 부산(PUS) 프랑스 파리(CDG) "
                )
            },
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7
    }

    try:
        response = requests.post(GROQ_API_URL, headers=headers, json=payload)
        response.raise_for_status()

        content = response.json()["choices"][0]["message"]["content"]

        # 두 번째 요청: 답변을 정돈된 문장으로 정리
        refinement_payload = {
            "model": GROQ_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "당신은 텍스트 편집 전문가입니다. "
                        "주어진 여행 추천 내용을 읽기 쉽고 정돈된 한국어 문장으로 정리해주세요. "
                        "한자, 일본어, 중국어가 포함되어있다면 반드시 제거해주세요. "
                        "문장을 자연스럽게 연결하고, 불필요한 반복을 제거하며, "
                        "전체적으로 일관성 있고 매력적인 추천 글로 만들어주세요. "
                        "지역명을 말할 때는 반드시 나라명 + 도시명(영어) + 해당 지역 인근 공항 iata code가 모두 포함되어있는지 검토하고, 포함하세요."
                    )
                },
                {"role": "user", "content": f"다음 여행 추천 내용을 정돈된 문장으로 정리해주세요:\n\n{content}"}
            ],
            "temperature": 0.5
        }

        try:
            refinement_response = requests.post(GROQ_API_URL, headers=headers, json=refinement_payload)
            refinement_response.raise_for_status()
            final_content = refinement_response.json()["choices"][0]["message"]["content"]
            
            # ISO3 코드 추출 (3자리 대문자 알파벳 패턴)
            iso3_codes = re.findall(r'\b[A-Z]{3}\b', final_content)
            
            return jsonify({
                "message": final_content,
                "iso3": iso3_codes
            })
        except Exception:
            # 정리 실패 시 원본 답변 반환
            iso3_codes = re.findall(r'\b[A-Z]{3}\b', content)
            return jsonify({
                "message": content,
                "iso3": iso3_codes
            })

    except requests.exceptions.HTTPError as http_err:
        print("🔴 HTTPError:", response.text)
        return jsonify({"error": f"{http_err} - {response.text}"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=5000)