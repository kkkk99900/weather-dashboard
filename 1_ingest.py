import os
import io
import json
import requests
from dotenv import load_dotenv
from minio import Minio

# 1. Nạp cấu hình từ .env
load_dotenv()

client = Minio(
    os.getenv("MINIO_ENDPOINT"),
    access_key=os.getenv("MINIO_ACCESS_KEY"),
    secret_key=os.getenv("MINIO_SECRET_KEY"),
    secure=os.getenv("MINIO_SECURE") == "True"
)
bucket_name = os.getenv("BUCKET_NAME")

# 2. Đảm bảo Bucket tồn tại
if not client.bucket_exists(bucket_name):
    client.make_bucket(bucket_name)

# 3. Kéo dữ liệu thời tiết Hà Nội từ Open-Meteo API
url = (
    "https://archive-api.open-meteo.com/v1/archive?"
    "latitude=21.0285&longitude=105.8542&start_date=2023-01-01&end_date=2023-12-31"
    "&hourly=temperature_2m,relative_humidity_2m,surface_pressure,precipitation"
    "&timezone=Asia%2FBangkok"
)
print(">>> Đang gọi API Open-Meteo...")
response = requests.get(url)
data = response.json()

# 4. Ghi trực tiếp dạng Stream lên MinIO Bronze Layer
json_bytes = json.dumps(data, indent=4).encode('utf-8')
object_path = "bronze/year=2023/hanoi_weather_raw.json"

client.put_object(
    bucket_name=bucket_name,
    object_name=object_path,
    data=io.BytesIO(json_bytes),
    length=len(json_bytes),
    content_type="application/json"
)

print(f" [Thành công] Đã lưu dữ liệu thô vào Bronze Layer tại: {object_path}")