import requests
import pandas as pd
from datetime import datetime
import uuid
import math
from sklearn.cluster import KMeans
from sklearn.preprocessing import MinMaxScaler

class OCRProcessor:
    def __init__(self, API_Secret_Key, OCR_URL):
        """
        OCRProcessor 클래스의 생성자입니다.

        Args:
            API_Secret_Key (str): OCR API를 호출하기 위한 시크릿 키
            OCR_URL (str): OCR API의 엔드포인트 URL
        """
        self.API_Secret_Key = API_Secret_Key
        self.OCR_URL = OCR_URL

    def send_ocr_request(self, image_url):
        """
        OCR API에 이미지 URL을 전송하여 텍스트를 추출하는 요청을 보냅니다.

        Args:
            image_url (str): 텍스트를 추출할 이미지의 URL

        Returns:
            dict or None: OCR API의 응답 결과. 성공할 경우 JSON 형식의 응답이 반환되며, 실패할 경우 None이 반환됩니다.
        """
        try:
            timestamp = datetime.now().microsecond
            header = {"X-OCR-SECRET": self.API_Secret_Key}
            content = {
                "images": [
                    {
                        "format": "jpg",
                        "name": "test",
                        "data": None,
                        "url": image_url
                    }
                ],
                "lang": "ko",
                "requestId": str(uuid.uuid4()),
                "resultType": "string",
                "timestamp": timestamp,
                "version": "V2"
            }
            response = requests.post(self.OCR_URL, json=content, headers=header)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"OCR 요청 실패: {e}")
            return None

    def get_text(self, df):
        """
        데이터프레임에서 텍스트를 추출하여 하나의 문자열로 반환합니다.

        Args:
            df (pandas.DataFrame): 텍스트를 추출할 데이터프레임. 'x', 'y', 'text' 열을 가져야 합니다.

        Returns:
            str: 데이터프레임에서 추출된 텍스트
        """

        image_content = ""
        prev_x = 0
        prev_y = 0
        for _, row in df.iterrows():
            x, y, text = row['x'], row['y'], row['text']
            if prev_x == 0 and prev_y == 0:
                image_content = text
            elif prev_x < x:
                image_content += " " + text
            else:
                image_content += "\n" + text
            prev_x, prev_y = x, y
        return image_content

    def find_optimal_clusters(self, df, max_clusters):
        """
        데이터프레임을 클러스터링하여 최적의 클러스터 개수를 찾고, 각 데이터포인트에 클러스터 레이블을 할당합니다.

        Args:
            df (pandas.DataFrame): 클러스터링할 데이터프레임. 'x', 'y' 열을 가져야 합니다.
            max_clusters (int): 최대 클러스터 개수

        Returns:
            pandas.DataFrame: 클러스터링 결과가 포함된 데이터프레임
        """
        data = df[['x', 'y']]
        data_scaled = MinMaxScaler().fit_transform(data)
        inertias = [KMeans(n_clusters=k, n_init='auto').fit(data_scaled).inertia_ for k in range(1, max_clusters + 1)]
        elbow_point = self._find_elbow_point(inertias, max_clusters)
        kmeans = KMeans(n_clusters=elbow_point, n_init='auto').fit(data_scaled)
        df['labels'] = kmeans.labels_
        return df

    def _find_elbow_point(self, inertias, max_clusters):
        """
        엘보우 메서드를 사용하여 최적의 클러스터 개수를 찾습니다.

        Args:
            inertias (list): 각 클러스터 개수에 대한 이너셔 값 리스트
            max_clusters (int): 최대 클러스터 개수

        Returns:
            int: 최적의 클러스터 개수
        """
        elbow_point, max_slope_diff = 1, -math.inf
        for i in range(1, max_clusters - 1):
            prev_slope = inertias[i] - inertias[i-1]
            next_slope = inertias[i+1] - inertias[i]
            slope_diff = prev_slope - next_slope
            if slope_diff > max_slope_diff:
                max_slope_diff = slope_diff
                elbow_point = i + 1
        return elbow_point

    def image_to_content(self, image_url):
        """
        이미지 URL을 입력으로 받아 OCR을 수행하고 텍스트 결과를 반환합니다.

        Args:
            image_url (str): OCR을 수행할 이미지의 URL

        Returns:
            str: OCR 결과로 추출된 텍스트
        """
        try:
            result = self.send_ocr_request(image_url)
            if result is None:
                return ""

            if result['images'][0]['inferResult'] == 'SUCCESS':
                fields = result['images'][0]['fields']
                df = pd.DataFrame([i['boundingPoly']['vertices'][0] for i in fields])
                df['text'] = [i['inferText'] for i in fields]
                df = self.find_optimal_clusters(df, max_clusters=5)
                content = "\n\n".join(df.groupby('labels').apply(self.get_text))
                return content.strip()
            else:
                print("OCR 요청 실패: 추론 결과가 실패했습니다.")
                return ""
        except Exception as e:
            print(f"예외 발생: {e}")
            return ""