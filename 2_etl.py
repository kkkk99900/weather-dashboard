import os
import time
import json
import pandas as pd
import io
from minio import Minio
from dotenv import load_dotenv

# Tải biến môi trường từ file .env
load_dotenv()

# -----------------------------------------
# BƯỚC 1: KHỞI TẠO KẾT NỐI MINIO
# -----------------------------------------
client = Minio(
    os.getenv("MINIO_ENDPOINT"),
    access_key=os.getenv("MINIO_ACCESS_KEY"),
    secret_key=os.getenv("MINIO_SECRET_KEY"),
    secure=os.getenv("MINIO_SECURE") == "True"
)

# Cấu hình bucket và đường dẫn chính xác theo thực tế
bucket_name = "weather-data"
object_name_json = "bronze/year=2023/hanoi_weather_raw.json"
object_name_parquet = "silver/year=2023/hanoi_weather_clean.parquet"

# Đảm bảo bucket weather-data tồn tại
if not client.bucket_exists(bucket_name):
    client.make_bucket(bucket_name)

# -----------------------------------------
# BƯỚC 2 & 3: EXTRACT & TRANSFORM (LÀM SẠCH)
# -----------------------------------------
print(f">>> Đang đọc dữ liệu từ: {bucket_name}/{object_name_json}...")

# Đo thời gian đọc và tính dung lượng file JSON
start_time = time.time()
response = client.get_object(bucket_name, object_name_json)
json_data = response.read()
json_read_time = time.time() - start_time
json_size_kb = len(json_data) / 1024
response.close()
response.release_conn()

# Parse JSON và đưa vào Pandas DataFrame
raw_dict = json.loads(json_data.decode('utf-8'))
df = pd.DataFrame(raw_dict['hourly'])

# Làm sạch dữ liệu: Chuyển đổi sang chuẩn datetime và xóa dữ liệu NaN
df['time'] = pd.to_datetime(df['time'])
df = df.dropna()
print(">>> Đã làm sạch dữ liệu thành công!")

# -----------------------------------------
# BƯỚC 4: TẢI LÊN (LOAD) & LƯU PARQUET
# -----------------------------------------
print(f">>> Đang nén và lưu Parquet lên: {bucket_name}/{object_name_parquet}...")

# Nén DataFrame sang Parquet trên bộ nhớ đệm (RAM) thay vì lưu xuống ổ cứng
parquet_buffer = io.BytesIO()
df.to_parquet(parquet_buffer, index=False, engine='pyarrow')
parquet_data = parquet_buffer.getvalue()
parquet_size_kb = len(parquet_data) / 1024

# Đẩy thẳng file Parquet từ bộ nhớ đệm lên MinIO
client.put_object(
    bucket_name=bucket_name,
    object_name=object_name_parquet,
    data=io.BytesIO(parquet_data),
    length=len(parquet_data)
)

# -----------------------------------------
# BƯỚC 5: ĐO LƯỜNG THỰC NGHIỆM ĐỌC PARQUET
# -----------------------------------------
start_time_pq = time.time()
pq_response = client.get_object(bucket_name, object_name_parquet)
pq_response.read()
pq_read_time = time.time() - start_time_pq
pq_response.close()
pq_response.release_conn()

# -----------------------------------------
# KẾT QUẢ BENCHMARK
# -----------------------------------------
print("\n" + "="*55)
print("BÁO CÁO BENCHMARK: JSON vs PARQUET")
print("="*55)
print(f"1. Định dạng JSON (Lớp Bronze):")
print(f"   - Kích thước : {json_size_kb:,.2f} KB")
print(f"   - Tốc độ đọc : {json_read_time:.5f} giây")
print("-" * 55)
print(f"2. Định dạng Parquet (Lớp Silver):")
print(f"   - Kích thước : {parquet_size_kb:,.2f} KB")
print(f"   - Tốc độ đọc : {pq_read_time:.5f} giây")
print(f"   - Hiệu năng  : Giảm {((json_size_kb - parquet_size_kb) / json_size_kb * 100):.2f}% dung lượng lưu trữ")
print("="*55 + "\n")

import matplotlib.pyplot as plt

# -----------------------------------------
# BƯỚC 6: VẼ ĐỒ THỊ TRỰC QUAN
# -----------------------------------------
print(">>> Đang tạo đồ thị báo cáo...")
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 5))

labels = ['JSON (Bronze)', 'Parquet (Silver)']
colors = ['#ff9999', '#66b3ff']

# Biểu đồ 1: Dung lượng
sizes = [json_size_kb, parquet_size_kb]
ax1.bar(labels, sizes, color=colors, width=0.5)
ax1.set_title('So sánh Dung lượng lưu trữ (KB)')
ax1.set_ylabel('Dung lượng (KB)')
for i, v in enumerate(sizes):
    ax1.text(i, v + 10, f"{v:,.2f}", ha='center', fontweight='bold')

# Biểu đồ 2: Tốc độ đọc
times = [json_read_time, pq_read_time]
ax2.bar(labels, times, color=colors, width=0.5)
ax2.set_title('So sánh Tốc độ đọc (Giây)')
ax2.set_ylabel('Thời gian (s)')
for i, v in enumerate(times):
    ax2.text(i, v + (max(times)*0.02), f"{v:.5f}", ha='center', fontweight='bold')

plt.tight_layout()
plt.savefig('benchmark_chart.png')
print(">>> Đã lưu đồ thị thành công vào file 'benchmark_chart.png'!")
