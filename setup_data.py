"""
Script cài đặt môi trường — chạy 1 lần sau khi git clone/pull
Tạo file fallback data/hanoi_2023.parquet từ MinIO
"""
import io, os, pathlib
import pandas as pd
from minio import Minio
from dotenv import load_dotenv

load_dotenv()

print("=== SETUP: Tạo file fallback từ MinIO ===")

# Tạo thư mục data nếu chưa có
pathlib.Path("data").mkdir(exist_ok=True)

client = Minio(
    os.getenv("MINIO_ENDPOINT", "localhost:9000"),
    access_key=os.getenv("MINIO_ACCESS_KEY", "admin"),
    secret_key=os.getenv("MINIO_SECRET_KEY", "password"),
    secure=False
)

try:
    r = client.get_object("weather-data", "silver/year=2023/hanoi_weather_clean.parquet")
    data = r.read()
    r.close(); r.release_conn()

    with open("data/hanoi_2023.parquet", "wb") as f:
        f.write(data)

    print(f"✅ Đã tạo: data/hanoi_2023.parquet ({len(data)/1024:.1f} KB)")
    print("   Dashboard sẽ dùng file này khi MinIO offline.")

except Exception as e:
    print(f"❌ Lỗi kết nối MinIO: {e}")
    print("   Hãy đảm bảo MinIO đang chạy: docker compose up -d minio")
    print("   Sau đó chạy lại script này.")
