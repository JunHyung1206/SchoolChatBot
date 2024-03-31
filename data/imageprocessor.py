import requests
import uuid
from datetime import datetime
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import MinMaxScaler
import math

class ImageProcessor:
    def __init__(self, api_secret_key, ocr_url):
        self.api_secret_key = api_secret_key
        self.ocr_url = ocr_url

    def send_ocr_request(self, image_url):
        try:
            timestamp = datetime.now().microsecond
            header = {"X-OCR-SECRET": self.api_secret_key}
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

            response = requests.post(self.ocr_url, json=content, headers=header)
            response.raise_for_status()  # 요청 실패 시 예외 발생
            result = response.json()
            return result
        except requests.exceptions.RequestException as e:
            print(f"OCR 요청 실패: {e}")
            return None

    def get_text(self, df):
        image_content = ""
        prev_x = 0
        prev_y = 0
        for _, row in df.iterrows():
            x = row['x']
            y = row['y']
            if prev_x == 0 and prev_y == 0:
                image_content = row['text']
            elif prev_x < x:
                image_content += " " + row['text']
            else:
                image_content += "\n" + row['text']
            prev_x = x
            prev_y = y
        return image_content

    def find_optimal_clusters(self, df, max_clusters):
        data = df[['x', 'y']]
        scaler = MinMaxScaler()
        data_scaled = scaler.fit_transform(data)

        inertias = []
        for k in range(1, max_clusters + 1):
            kmeans = KMeans(n_clusters=k, n_init='auto')
            kmeans.fit(data_scaled)
            inertias.append(kmeans.inertia_)

        elbow_point = self.find_elbow_point(inertias, max_clusters)
        kmeans = KMeans(n_clusters=elbow_point, n_init='auto')
        kmeans.fit(data_scaled)
        df['labels'] = kmeans.labels_
        return df

    def find_elbow_point(self, inertias, max_clusters):
        elbow_point = 1
        max_slope_diff = -math.inf
        for i in range(1, max_clusters - 1):
            prev_slope = inertias[i] - inertias[i-1]
            next_slope = inertias[i+1] - inertias[i]
            slope_diff = prev_slope - next_slope
            if slope_diff > max_slope_diff:
                max_slope_diff = slope_diff
                elbow_point = i
        return elbow_point

    def image_to_content(self, image_url):
        result = self.send_ocr_request(image_url)
        if result is None:
            return ""

        if result['images'][0]['inferResult'] == 'SUCCESS':
            fields = result['images'][0]['fields']
            df = pd.DataFrame([i['boundingPoly']['vertices'][0] for i in fields])
            df['text'] = [i['inferText'] for i in fields]
            df = self.find_optimal_clusters(df, max_clusters=5)
            content = ""
            for label in df['labels'].unique():
                content += self.get_text(df[df['labels'] == label]) + '\n\n'
            content = content.strip()
            return content
        else:
            print("OCR 요청 실패: 추론 결과가 실패했습니다.")
            return ""
