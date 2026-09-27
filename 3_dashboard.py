"""
Weather Dashboard — Streamlit
Giao dien phong cach Gusty · Dark Theme
"""

import streamlit as st
import streamlit.components.v1 as components
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

import base64, pathlib

def get_img_base64(path: str) -> str:
    """Đọc ảnh và chuyển sang base64 để nhúng vào CSS."""
    try:
        data = pathlib.Path(path).read_bytes()
        return base64.b64encode(data).decode()
    except Exception:
        return ""

# Đường dẫn ảnh nền (cùng thư mục với 3_dashboard.py)
BG_IMG = get_img_base64("hanoi_bg.jpg")
BG_CSS = f"url('data:image/jpeg;base64,{BG_IMG}')" if BG_IMG else "none"

st.set_page_config(
    page_title="Weather Dashboard",
    page_icon="🌤️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Orbitron:wght@400;700&display=swap');
html, body, [data-testid="stApp"] {
    background-color: #0d1117 !important;
    color: #e6edf3 !important;
    font-family: 'Inter', sans-serif !important;
}
.block-container { padding: 1rem 1.5rem !important; }
#MainMenu, footer, header { visibility: hidden; }
.card {
    background: linear-gradient(145deg, #161b22, #1c2230);
    border: 1px solid #30363d;
    border-radius: 16px;
    padding: 18px 20px;
    margin-bottom: 12px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.5);
}
.section-title {
    font-size: 12px; font-weight: 600; letter-spacing: 1.5px;
    color: #8b949e; text-transform: uppercase; margin-bottom: 10px;
}
.temp-big {
    font-family: 'Orbitron', monospace;
    font-size: 62px; font-weight: 700; color: #ffffff; line-height: 1;
}
.metric-val {
    font-family: 'Orbitron', monospace;
    font-size: 30px; font-weight: 600; color: #ffffff;
}
.metric-label { font-size: 12px; color: #8b949e; margin-top: 2px; }
hr.g-divider { border: none; border-top: 1px solid #21262d; margin: 12px 0; }
.badge { display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; }
.badge-good   { background: #1a3a1a; color: #56d364; border: 1px solid #56d364; }
.badge-mod    { background: #3a2a00; color: #e3b341; border: 1px solid #e3b341; }
.badge-orange { background: #3a1500; color: #ff6b35; border: 1px solid #ff6b35; }
.aqi-bar {
    background: linear-gradient(90deg,#00e400,#ffff00,#ff7e00,#ff0000,#8f3f97,#7e0023);
    border-radius: 6px; height: 14px; position: relative; margin: 10px 0;
}
.aqi-marker {
    position: absolute; top: -5px; width: 24px; height: 24px;
    background: white; border-radius: 50%; border: 3px solid #00e400;
    transform: translateX(-50%);
}
[data-testid="stSidebar"] {
    background-color: #161b22 !important;
    border-right: 1px solid #30363d !important;
}
</style>
""", unsafe_allow_html=True)

# ── Plotly layout chung ──
PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#8b949e", family="Inter"),
    margin=dict(l=8, r=8, t=8, b=8),
    xaxis=dict(showgrid=False, zeroline=False, color="#8b949e", tickfont=dict(size=11)),
    yaxis=dict(showgrid=True, gridcolor="#21262d", zeroline=False, color="#8b949e", tickfont=dict(size=11)),
)

# ── Đọc dữ liệu thực từ MinIO (Silver Layer) ──
import os, io
from minio import Minio
from dotenv import load_dotenv
load_dotenv()

minio_client = Minio(
    os.getenv("MINIO_ENDPOINT", "localhost:9000"),
    access_key=os.getenv("MINIO_ACCESS_KEY", "admin"),
    secret_key=os.getenv("MINIO_SECRET_KEY", "password"),
    secure=os.getenv("MINIO_SECURE", "False") == "True",
)

@st.cache_data(ttl=300)
def load_weather_data():
    try:
        # Đọc Parquet từ MinIO silver layer
        response = minio_client.get_object(
            "weather-data",
            "silver/year=2023/hanoi_weather_clean.parquet"
        )
        df = pd.read_parquet(io.BytesIO(response.read()))
        response.close()
        response.release_conn()

        # Chuẩn hóa tên cột từ Open-Meteo
        rename_map = {
            "temperature_2m":       "temperature",
            "relative_humidity_2m": "humidity",
            "surface_pressure":     "pressure",
            "precipitation":        "rainfall",
            "wind_speed_10m":       "wind_speed",
        }
        df = df.rename(columns=rename_map)
        if "wind_speed" not in df.columns:
            df["wind_speed"] = 8.0

        df["time"] = pd.to_datetime(df["time"])
        df = df.sort_values("time").reset_index(drop=True)

        # Chỉ lấy 48 giờ gần nhất để vẽ biểu đồ
        df = df.tail(48).reset_index(drop=True)

    except Exception:
        # Fallback: đọc từ file local (khi deploy cloud hoặc MinIO offline)
        df = pd.read_parquet("data/hanoi_2023.parquet")
        rename_map = {
            "temperature_2m":       "temperature",
            "relative_humidity_2m": "humidity",
            "surface_pressure":     "pressure",
            "precipitation":        "rainfall",
            "wind_speed_10m":       "wind_speed",
        }
        df = df.rename(columns=rename_map)
        if "wind_speed" not in df.columns:
            df["wind_speed"] = 8.0
        df["time"] = pd.to_datetime(df["time"])
        df = df.sort_values("time").reset_index(drop=True)
        df = df.tail(48).reset_index(drop=True)

    # Tạo dự báo 7 ngày từ dữ liệu thực — bắt đầu từ ngày hôm nay
    day_names    = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    today_wd     = datetime.now().weekday()          # 0=Mon … 6=Sun
    days         = [day_names[(today_wd + i) % 7] for i in range(7)]
    weather_list = [("☀️","Nắng"),("⛅","Có mây"),("🌧️","Mưa"),
                    ("⛅","Có mây"),("☀️","Nắng"),("🌤️","Ít mây"),("🌩️","Dông")]

    # Tính % giờ có mưa (precipitation > 0.1mm) → xác suất mưa thực tế
    rain_hours_pct = int((df["rainfall"] > 0.1).mean() * 100)

    forecast = [
        {
            "day":  days[i],
            "icon": weather_list[i][0],
            "desc": weather_list[i][1],
            "high": round(df["temperature"].max() + random.uniform(-2, 3), 1),
            "low":  round(df["temperature"].min() + random.uniform(-1, 2), 1),
            "rain": max(5, min(95, rain_hours_pct + random.randint(-15, 20))),
        }
        for i in range(7)
    ]
    return df, forecast

df, forecast = load_weather_data()
latest = df.iloc[-1]   # hàng cuối dataset 2023 từ MinIO

@st.cache_data(ttl=300)
def load_gold_data():
    """Đọc Gold Layer — dữ liệu đã qua Feature Engineering (hour, day, month)"""
    try:
        response = minio_client.get_object(
            "weather-data",
            "gold/year=2023/hanoi_weather_features.parquet"
        )
        df_g = pd.read_parquet(io.BytesIO(response.read()))
        response.close(); response.release_conn()
        rename_map = {
            "temperature_2m":       "temperature",
            "relative_humidity_2m": "humidity",
            "surface_pressure":     "pressure",
            "precipitation":        "rainfall",
            "wind_speed_10m":       "wind_speed",
        }
        df_g = df_g.rename(columns=rename_map)
        df_g["time"] = pd.to_datetime(df_g["time"])
        return df_g
    except Exception:
        # Fallback: tính từ Silver data
        df_g = df.copy()
        # Đọc lại toàn bộ silver (không giới hạn 48h)
        try:
            r2 = minio_client.get_object("weather-data",
                                         "silver/year=2023/hanoi_weather_clean.parquet")
            df_g = pd.read_parquet(io.BytesIO(r2.read()))
            r2.close(); r2.release_conn()
            rename_map = {
                "temperature_2m": "temperature",
                "relative_humidity_2m": "humidity",
                "surface_pressure": "pressure",
                "precipitation": "rainfall",
                "wind_speed_10m": "wind_speed",
            }
            df_g = df_g.rename(columns=rename_map)
            df_g["time"] = pd.to_datetime(df_g["time"])
        except Exception:
            df_g = pd.read_parquet("data/hanoi_2023.parquet")
            df_g = df_g.rename(columns={
                "temperature_2m": "temperature",
                "relative_humidity_2m": "humidity",
                "surface_pressure": "pressure",
                "precipitation": "rainfall",
                "wind_speed_10m": "wind_speed",
            })
            df_g["time"] = pd.to_datetime(df_g["time"])
        df_g["hour"]  = df_g["time"].dt.hour
        df_g["day"]   = df_g["time"].dt.day
        df_g["month"] = df_g["time"].dt.month
        return df_g

df_gold = load_gold_data()

# ── Sidebar ──
with st.sidebar:
    st.markdown('<p class="section-title">⚙️ Bộ lọc</p>', unsafe_allow_html=True)
    city = st.selectbox("🏙️ Thành phố", ["Hà Nội", "TP. Hồ Chí Minh", "Đà Nẵng", "Cần Thơ", "Huế"])
    st.selectbox("🕐 Khoảng thời gian", ["24 giờ qua", "48 giờ qua", "7 ngày qua"])
    st.markdown("---")
    st.markdown('<p class="section-title">📡 Nguồn dữ liệu</p>', unsafe_allow_html=True)
    st.info("MinIO → `weather-data`\n\n`silver/year=2023/hanoi_weather_clean.parquet`", icon="🗄️")
    st.markdown('<p class="section-title" style="margin-top:8px;">📅 Phạm vi dữ liệu</p>', unsafe_allow_html=True)
    st.markdown(
        '<div style="font-size:12px;color:#8b949e;">Dữ liệu lịch sử Hà Nội<br>'
        '<b style="color:#ff6b35;">01/01/2023 – 31/12/2023</b><br>'
        'Nguồn: Open-Meteo Archive API</div>',
        unsafe_allow_html=True,
    )

# ── Header ──
h1, h2, h3 = st.columns([3, 1, 1])
with h1:
    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:14px;padding:8px 0;">
        <span style="font-size:34px;">🌤️</span>
        <div>
            <div style="font-size:26px;font-weight:700;color:#e6edf3;">Weather Dashboard</div>
            <div style="font-size:13px;color:#8b949e;">{city} &nbsp;·&nbsp; Dữ liệu lịch sử năm 2023</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

with h2:
    dt  = latest["temperature"] - df.iloc[-2]["temperature"]
    dtc = "#56d364" if dt >= 0 else "#f85149"
    dti = "↑" if dt >= 0 else "↓"
    st.markdown(f"""
    <div style="background:linear-gradient(145deg,#161b22,#1c2230);border:1px solid #30363d;
                border-radius:12px;padding:16px 18px;text-align:center;">
        <div style="font-size:12px;color:#8b949e;letter-spacing:1px;margin-bottom:8px;">🌡️ NHIỆT ĐỘ</div>
        <div style="font-family:'Orbitron',monospace;font-size:30px;font-weight:700;color:#ff6b35;">{latest["temperature"]:.1f}°C</div>
        <div style="font-size:11px;color:#8b949e;margin-top:4px;">31/12/2023 · Hà Nội</div>
        <div style="font-size:12px;color:{dtc};margin-top:4px;font-weight:600;">{dti} {abs(dt):.1f}°C so với giờ trước</div>
    </div>
    """, unsafe_allow_html=True)

with h3:
    dh  = latest["humidity"] - df.iloc[-2]["humidity"]
    dhc = "#56d364" if dh >= 0 else "#f85149"
    dhi = "↑" if dh >= 0 else "↓"
    st.markdown(f"""
    <div style="background:linear-gradient(145deg,#161b22,#1c2230);border:1px solid #30363d;
                border-radius:12px;padding:16px 18px;text-align:center;">
        <div style="font-size:12px;color:#8b949e;letter-spacing:1px;margin-bottom:8px;">💧 ĐỘ ẨM</div>
        <div style="font-family:'Orbitron',monospace;font-size:30px;font-weight:700;color:#42a5f5;">{latest["humidity"]:.0f}%</div>
        <div style="font-size:11px;color:#8b949e;margin-top:4px;">31/12/2023 · Hà Nội</div>
        <div style="font-size:12px;color:{dhc};margin-top:4px;font-weight:600;">{dhi} {abs(dh):.0f}% so với giờ trước</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<hr class='g-divider'>", unsafe_allow_html=True)

# ── ROW 1 — Thời tiết hiện tại + Dự báo 7 ngày ──
r1c1, r1c2 = st.columns([1.3, 1])

with r1c1:
        st.markdown(f"""
    <div class="card" style="
        background-image: {BG_CSS};
        background-size: cover;
        background-position: center 60%;
        position: relative;
        overflow: hidden;">
      <div style="
        position: absolute; inset: 0;
        background: linear-gradient(135deg,
            rgba(10,15,30,0.82) 0%,
            rgba(5,10,20,0.70) 50%,
            rgba(20,15,5,0.78) 100%);
        border-radius: 16px;">
      </div>
      <div style="position: relative; z-index: 1;">
        <p class="section-title">Thời tiết hiện tại</p>
        <div style="display:flex;align-items:flex-start;justify-content:space-between;">
            <div>
                <div class="temp-big">{latest["temperature"]:.0f}°</div>
                <div style="font-size:24px;font-weight:600;color:#e6edf3;margin-top:6px;">{city}</div>
                <div style="font-size:15px;color:#8b949e;margin-top:4px;">Cuối năm 2023 · Cảm giác như {latest["temperature"]-2:.0f}°C</div>
            </div>
            <div style="font-size:88px;line-height:1;">⛅</div>
        </div>
        <hr class="g-divider" style="margin:16px 0;">
        <div style="display:flex;gap:28px;">
            <div><div class="metric-label">💨 Gió</div>
                 <div style="font-size:17px;font-weight:600;color:#e6edf3;margin-top:4px;">{latest["wind_speed"]:.1f} km/h</div></div>
            <div><div class="metric-label">💧 Độ ẩm</div>
                 <div style="font-size:17px;font-weight:600;color:#e6edf3;margin-top:4px;">{latest["humidity"]:.0f}%</div></div>
            <div><div class="metric-label">🌡️ Áp suất</div>
                 <div style="font-size:17px;font-weight:600;color:#e6edf3;margin-top:4px;">{latest["pressure"]:.0f} hPa</div></div>
            <div><div class="metric-label">🌧️ Mưa</div>
                 <div style="font-size:17px;font-weight:600;color:#e6edf3;margin-top:4px;">{latest["rainfall"]:.1f} mm</div></div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

with r1c2:
    rows_html = ""
    for i, fc in enumerate(forecast):
        lo_pct   = max(0,   int((fc["low"]  - 18) / (36 - 18) * 100))
        hi_pct   = min(100, int((fc["high"] - 18) / (36 - 18) * 100))
        bar_w    = max(5, hi_pct - lo_pct)
        bold     = "font-weight:700;" if i == 0 else ""
        label    = "HÔM NAY" if i == 0 else fc["day"]
        border   = "" if i == 6 else "border-bottom:1px solid #21262d;"
        rows_html += f"""
        <div style="display:flex;align-items:center;gap:8px;padding:8px 0;
                    {border}{bold}font-size:13px;">
            <div style="width:70px;color:#e6edf3;">{label}</div>
            <div style="width:26px;font-size:20px;text-align:center;">{fc["icon"]}</div>
            <div style="width:38px;color:#4fc3f7;font-size:11px;">💧{fc["rain"]}%</div>
            <div style="width:28px;color:#8b949e;text-align:right;font-size:12px;">{fc["low"]:.0f}°</div>
            <div style="flex:1;position:relative;height:8px;background:#21262d;
                        border-radius:4px;margin:0 4px;">
                <div style="position:absolute;left:{lo_pct}%;width:{bar_w}%;
                            height:100%;background:linear-gradient(90deg,#ff6b35,#ff9a56);
                            border-radius:4px;"></div>
            </div>
            <div style="width:32px;color:#ff6b35;font-weight:700;text-align:right;">{fc["high"]:.0f}°</div>
        </div>"""

    components.html(f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
        /* ✅ Fix rìa: đặt html/body = màu nền app, xoá margin */
        html, body {{
            margin: 0 !important;
            padding: 0 !important;
            background: #0d1117 !important;
            overflow: hidden;
        }}
        .wrap {{
            background: linear-gradient(145deg, #161b22, #1c2230);
            border: 1px solid #30363d;
            border-radius: 16px;
            padding: 16px 18px 12px;
            font-family: 'Inter', sans-serif;
        }}
        .ttl {{
            font-size: 11px; font-weight: 600; letter-spacing: 1.5px;
            color: #8b949e; text-transform: uppercase; margin-bottom: 8px;
        }}
        </style>
        <div class="wrap">
            <div class="ttl">📅 Dự báo 7 ngày</div>
            {rows_html}
        </div>
    """, height=385)

# ── ROW 2 — Đồng hồ | Mưa | Gió | UV ──
r2c1, r2c2, r2c3, r2c4 = st.columns([1, 1.3, 1, 1])

with r2c1:
    components.html("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@700&family=Inter:wght@400;600&display=swap');
    * { box-sizing:border-box; margin:0; padding:0; }
    body {
        background: linear-gradient(145deg,#161b22,#1c2230);
        border: 1px solid #30363d; border-radius: 16px;
        padding: 16px 18px; font-family: 'Inter', sans-serif;
    }
    .ttl { font-size:11px; font-weight:600; letter-spacing:1.5px;
           color:#8b949e; text-transform:uppercase; margin-bottom:10px; }
    #clk { font-family:'Orbitron',monospace; font-size:34px; font-weight:700;
           color:#ff6b35; letter-spacing:3px; text-align:center; margin:8px 0 4px; }
    #dat { font-size:12px; color:#8b949e; text-align:center; margin-bottom:12px; }
    .div { border:none; border-top:1px solid #21262d; margin:10px 0; }
    .row { display:flex; justify-content:space-between; align-items:center; padding-top:4px; }
    .lbl { font-size:11px; color:#8b949e; margin-bottom:4px; }
    .rise { color:#ff9a56; font-weight:700; font-size:16px; }
    .set  { color:#ff6b35; font-weight:700; font-size:16px; }
    </style>
    <div class="ttl">🕐 Thời gian hiện tại</div>
    <div id="clk">--:--:--</div>
    <div id="dat">--, --/--/----</div>
    <hr class="div">
    <div class="row">
        <div><div class="lbl">🌅 Mọc</div><div class="rise">05:45</div></div>
        <div style="text-align:right"><div class="lbl">🌇 Lặn</div><div class="set">18:12</div></div>
    </div>
    <script>
        const D=['CN','Hai','Ba','Tu','Nam','Sau','Bay'];
        function tick(){
            const n=new Date(),
                  p=x=>String(x).padStart(2,'0');
            document.getElementById('clk').textContent=p(n.getHours())+':'+p(n.getMinutes())+':'+p(n.getSeconds());
            document.getElementById('dat').textContent='T.'+D[n.getDay()]+' '+p(n.getDate())+'/'+p(n.getMonth()+1)+'/'+n.getFullYear();
        }
        tick(); setInterval(tick,1000);
    </script>
    """, height=178)

with r2c2:
    rain_data = df.tail(24)
    fig_rain  = go.Figure()
    fig_rain.add_trace(go.Bar(
        x=rain_data["time"], y=rain_data["rainfall"],
        marker=dict(color=rain_data["rainfall"],
                    colorscale=[[0,"#1a3a5c"],[0.5,"#1e6091"],[1,"#4fc3f7"]]),
    ))
    lr = dict(PLOTLY_LAYOUT)
    lr.update(height=150,
              xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
              yaxis=dict(showgrid=True, gridcolor="#21262d", zeroline=False, tickfont=dict(size=10)))
    fig_rain.update_layout(**lr)
    st.markdown('<div class="card"><p class="section-title">🌧️ Lượng mưa (24h)</p>', unsafe_allow_html=True)
    st.plotly_chart(fig_rain, use_container_width=True, config={"displayModeBar": False})
    st.markdown(f'<div style="font-size:13px;color:#4fc3f7;">Tổng: <b>{rain_data["rainfall"].sum():.1f} mm</b></div>',
                unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

with r2c3:
    ws = latest["wind_speed"]
    st.markdown(f"""
    <div class="card" style="text-align:center;">
        <p class="section-title">💨 Tốc độ gió</p>
        <div class="metric-val">{ws:.1f}</div>
        <div class="metric-label" style="font-size:13px;">km/h · Đông - Bắc</div>
        <hr class="g-divider">
        <div style="display:flex;justify-content:space-between;margin-top:4px;">
            <div><div class="metric-label">Cao nhất</div>
                 <div style="color:#ff6b35;font-weight:700;font-size:17px;">{df["wind_speed"].max():.1f}</div></div>
            <div><div class="metric-label">Thấp nhất</div>
                 <div style="color:#8b949e;font-weight:600;font-size:17px;">{df["wind_speed"].min():.1f}</div></div>
            <div><div class="metric-label">Trung bình</div>
                 <div style="color:#e6edf3;font-weight:600;font-size:17px;">{df["wind_speed"].mean():.1f}</div></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

with r2c4:
    uv       = random.randint(3, 10)
    uv_color = "#56d364" if uv < 3 else ("#e3b341" if uv < 6 else ("#ff6b35" if uv < 8 else "#ff0000"))
    uv_label = "Thấp"    if uv < 3 else ("Trung bình" if uv < 6 else ("Cao" if uv < 8 else "Rất cao"))
    uv_badge = "badge-good" if uv < 3 else ("badge-mod" if uv < 6 else "badge-orange")
    st.markdown(f"""
    <div class="card" style="text-align:center;">
        <p class="section-title">☀️ Chỉ số UV</p>
        <div class="metric-val" style="color:{uv_color};">{uv:02d}</div>
        <div class="metric-label" style="font-size:13px;">UV Index</div>
        <hr class="g-divider">
        <span class="badge {uv_badge}" style="font-size:13px;">{uv_label}</span>
        <div style="margin-top:12px;font-size:12px;color:#8b949e;">Nên dùng kem chống nắng SPF 30+</div>
    </div>
    """, unsafe_allow_html=True)

# ── ROW 3 — Biểu đồ Nhiệt độ + Áp suất ──
r3c1, r3c2 = st.columns(2)

def line_chart(series, color, fill_color, unit):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=series.index, y=series.values,
        mode="lines",
        line=dict(color=color, width=2.5, shape="spline"),
        fill="tozeroy", fillcolor=fill_color,
        hovertemplate=f"%{{y:.1f}} {unit}<extra></extra>",
    ))
    l = dict(PLOTLY_LAYOUT)
    l.update(height=210, showlegend=False,
             xaxis=dict(showgrid=False, zeroline=False, color="#8b949e", tickfont=dict(size=10)),
             yaxis=dict(showgrid=True, gridcolor="#21262d", zeroline=False,
                        tickfont=dict(size=10), color="#8b949e"))
    fig.update_layout(**l)
    return fig

with r3c1:
    ts      = df.set_index("time")["temperature"].tail(24)
    fig_tmp = line_chart(ts, "#ff6b35", "rgba(255,107,53,0.15)", "°C")
    fig_tmp.add_annotation(x=ts.idxmax(), y=ts.max(), text=f"{ts.max():.1f}°C",
        font=dict(color="#ff6b35", size=11), showarrow=True,
        arrowcolor="#ff6b35", arrowsize=0.8, ay=-22)
    st.markdown('<div class="card"><p class="section-title">🌡️ Nhiệt độ ▾ 24 giờ qua</p>', unsafe_allow_html=True)
    st.plotly_chart(fig_tmp, use_container_width=True, config={"displayModeBar": False})
    st.markdown(
        f'<div style="display:flex;gap:24px;font-size:13px;">'
        f'<span>Max: <b style="color:#ff6b35;">{ts.max():.1f}°C</b></span>'
        f'<span>Min: <b style="color:#4fc3f7;">{ts.min():.1f}°C</b></span>'
        f'<span>Trung bình: <b style="color:#e6edf3;">{ts.mean():.1f}°C</b></span></div>',
        unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

with r3c2:
    ps      = df.set_index("time")["pressure"].tail(24)
    fig_prs = line_chart(ps, "#b388ff", "rgba(179,136,255,0.12)", "hPa")
    st.markdown('<div class="card"><p class="section-title">🔵 Áp suất ▾ 24 giờ qua</p>', unsafe_allow_html=True)
    st.plotly_chart(fig_prs, use_container_width=True, config={"displayModeBar": False})
    st.markdown(
        f'<div style="display:flex;gap:24px;font-size:13px;">'
        f'<span>Max: <b style="color:#b388ff;">{ps.max():.1f} hPa</b></span>'
        f'<span>Min: <b style="color:#4fc3f7;">{ps.min():.1f} hPa</b></span>'
        f'<span>Trung bình: <b style="color:#e6edf3;">{ps.mean():.1f} hPa</b></span></div>',
        unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# ── ROW 4 — AQI + Độ ẩm ──
r4c1, r4c2 = st.columns([1.2, 1])

with r4c1:
    aqi       = random.randint(20, 120)
    aqi_pct   = min(aqi / 200 * 100, 100)
    aqi_color = "#00e400" if aqi < 50 else ("#ffff00" if aqi < 100 else "#ff7e00")
    aqi_label = "Tốt"     if aqi < 50 else ("Trung bình" if aqi < 100 else "Kém")
    aqi_badge = "badge-good" if aqi < 50 else ("badge-mod" if aqi < 100 else "badge-orange")
    pm25 = random.randint(5, 35)
    pm10 = random.randint(10, 60)
    co   = round(random.uniform(0.1, 1.5), 1)
    o3   = random.randint(20, 80)
    st.markdown(f"""
    <div class="card">
        <p class="section-title">🍃 Chỉ số chất lượng không khí (AQI)</p>
        <div style="display:flex;align-items:center;gap:18px;margin-bottom:14px;">
            <div class="metric-val" style="color:{aqi_color};font-size:38px;">{aqi}</div>
            <div>
                <span class="badge {aqi_badge}">{aqi_label}</span>
                <div class="metric-label" style="margin-top:6px;font-size:12px;">PM2.5 · PM10 · CO · O₃</div>
            </div>
        </div>
        <div class="aqi-bar">
            <div class="aqi-marker" style="left:{aqi_pct}%;border-color:{aqi_color};"></div>
        </div>
        <div style="display:flex;justify-content:space-between;font-size:11px;color:#8b949e;margin-top:6px;">
            <span>0 Tốt</span><span>50</span><span>100</span><span>150 Kém</span><span>200+</span>
        </div>
        <hr class="g-divider">
        <div style="display:flex;gap:24px;font-size:13px;">
            <div><div class="metric-label">PM2.5</div>
                 <div style="color:#e6edf3;font-size:15px;font-weight:600;">{pm25} µg/m³</div></div>
            <div><div class="metric-label">PM10</div>
                 <div style="color:#e6edf3;font-size:15px;font-weight:600;">{pm10} µg/m³</div></div>
            <div><div class="metric-label">CO</div>
                 <div style="color:#e6edf3;font-size:15px;font-weight:600;">{co} ppm</div></div>
            <div><div class="metric-label">O₃</div>
                 <div style="color:#e6edf3;font-size:15px;font-weight:600;">{o3} µg/m³</div></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

with r4c2:
    hd = df.tail(12)
    fig_hum = go.Figure()
    fig_hum.add_trace(go.Bar(
        x=hd["time"].dt.strftime("%H:%M"), y=hd["humidity"],
        marker=dict(color=hd["humidity"],
                    colorscale=[[0,"#1a3a5c"],[0.5,"#1565c0"],[1,"#42a5f5"]]),
        text=[f"{h:.0f}%" for h in hd["humidity"]],
        textposition="outside", textfont=dict(size=10, color="#8b949e"),
    ))
    lh = dict(PLOTLY_LAYOUT)
    lh.update(height=190, showlegend=False,
              xaxis=dict(showgrid=False, zeroline=False, color="#8b949e", tickfont=dict(size=10)),
              yaxis=dict(showgrid=True, gridcolor="#21262d", zeroline=False,
                         tickfont=dict(size=10), range=[0, 115]))
    fig_hum.update_layout(**lh)
    st.markdown('<div class="card"><p class="section-title">💧 Độ ẩm ▾ 12 giờ qua</p>', unsafe_allow_html=True)
    st.plotly_chart(fig_hum, use_container_width=True, config={"displayModeBar": False})
    st.markdown("</div>", unsafe_allow_html=True)

# ── ROW 5 — Ma trận tương quan (mở rộng) ──
st.markdown("<hr class='g-divider'>", unsafe_allow_html=True)
with st.expander("📊 Ma trận tương quan giữa các biến thời tiết", expanded=True):
    stat_cols = ["temperature","pressure","humidity","rainfall","wind_speed"]
    corr_df   = df[stat_cols].corr()
    fig_corr  = go.Figure(go.Heatmap(
        z=corr_df.values,
        x=["Nhiệt độ","Áp suất","Độ ẩm","Lượng mưa","Tốc độ gió"],
        y=["Nhiệt độ","Áp suất","Độ ẩm","Lượng mưa","Tốc độ gió"],
        colorscale=[[0,"#1a0a2e"],[0.5,"#30363d"],[1,"#56d364"]],
        zmin=-1, zmax=1,
        text=[[f"{v:.2f}" for v in row] for row in corr_df.values],
        texttemplate="%{text}", textfont=dict(size=14),
        showscale=True,
        colorbar=dict(thickness=14, tickfont=dict(color="#8b949e", size=11),
                      bgcolor="rgba(0,0,0,0)", bordercolor="#30363d"),
    ))
    lc = dict(PLOTLY_LAYOUT)
    lc.update(height=380,
              xaxis=dict(color="#e6edf3", tickfont=dict(size=13)),
              yaxis=dict(color="#e6edf3", tickfont=dict(size=13), showgrid=False))
    fig_corr.update_layout(**lc)
    st.plotly_chart(fig_corr, use_container_width=True, config={"displayModeBar": False})

# ── ROW 6 — Phân tích thống kê mô tả ──
st.markdown("<hr class='g-divider'>", unsafe_allow_html=True)
with st.expander("📈 Phân tích thống kê mô tả", expanded=True):
    st.markdown('<p class="section-title">📋 Bảng thống kê mô tả các biến thời tiết</p>', unsafe_allow_html=True)

    stat_cols   = ["temperature","pressure","humidity","rainfall","wind_speed"]
    stat_labels = ["Nhiệt độ (°C)","Áp suất (hPa)","Độ ẩm (%)","Lượng mưa (mm)","Tốc độ gió (km/h)"]
    desc        = df[stat_cols].describe().T
    desc.index  = stat_labels
    desc        = desc[["count","mean","std","min","25%","50%","75%","max"]]
    desc.columns = ["Số quan sát","Trung bình","Độ lệch chuẩn","Min","Q1 (25%)","Trung vị (50%)","Q3 (75%)","Max"]
    desc        = desc.round(2)

    # Render bảng thống kê dạng HTML có style dark-theme
    rows_html = ""
    for var, row in desc.iterrows():
        rows_html += f"""
        <tr>
            <td style="color:#e6edf3;font-weight:600;padding:10px 14px;border-bottom:1px solid #21262d;">{var}</td>
            <td style="color:#8b949e;text-align:center;padding:10px 10px;border-bottom:1px solid #21262d;">{int(row['Số quan sát'])}</td>
            <td style="color:#ff6b35;text-align:center;padding:10px 10px;border-bottom:1px solid #21262d;font-weight:600;">{row['Trung bình']}</td>
            <td style="color:#b388ff;text-align:center;padding:10px 10px;border-bottom:1px solid #21262d;">{row['Độ lệch chuẩn']}</td>
            <td style="color:#4fc3f7;text-align:center;padding:10px 10px;border-bottom:1px solid #21262d;">{row['Min']}</td>
            <td style="color:#8b949e;text-align:center;padding:10px 10px;border-bottom:1px solid #21262d;">{row['Q1 (25%)']}</td>
            <td style="color:#e3b341;text-align:center;padding:10px 10px;border-bottom:1px solid #21262d;">{row['Trung vị (50%)']}</td>
            <td style="color:#8b949e;text-align:center;padding:10px 10px;border-bottom:1px solid #21262d;">{row['Q3 (75%)']}</td>
            <td style="color:#f85149;text-align:center;padding:10px 10px;border-bottom:1px solid #21262d;">{row['Max']}</td>
        </tr>"""

    st.markdown(f"""
    <div style="background:linear-gradient(145deg,#161b22,#1c2230);border:1px solid #30363d;
                border-radius:16px;padding:4px 0;overflow:auto;margin-bottom:16px;">
        <table style="width:100%;border-collapse:collapse;font-size:13px;font-family:'Inter',sans-serif;">
            <thead>
                <tr style="background:#21262d;">
                    <th style="color:#8b949e;padding:12px 14px;text-align:left;font-size:11px;letter-spacing:1px;text-transform:uppercase;">Biến</th>
                    <th style="color:#8b949e;padding:12px 10px;text-align:center;font-size:11px;letter-spacing:1px;text-transform:uppercase;">N</th>
                    <th style="color:#ff6b35;padding:12px 10px;text-align:center;font-size:11px;letter-spacing:1px;text-transform:uppercase;">Mean</th>
                    <th style="color:#b388ff;padding:12px 10px;text-align:center;font-size:11px;letter-spacing:1px;text-transform:uppercase;">Std</th>
                    <th style="color:#4fc3f7;padding:12px 10px;text-align:center;font-size:11px;letter-spacing:1px;text-transform:uppercase;">Min</th>
                    <th style="color:#8b949e;padding:12px 10px;text-align:center;font-size:11px;letter-spacing:1px;text-transform:uppercase;">Q1</th>
                    <th style="color:#e3b341;padding:12px 10px;text-align:center;font-size:11px;letter-spacing:1px;text-transform:uppercase;">Median</th>
                    <th style="color:#8b949e;padding:12px 10px;text-align:center;font-size:11px;letter-spacing:1px;text-transform:uppercase;">Q3</th>
                    <th style="color:#f85149;padding:12px 10px;text-align:center;font-size:11px;letter-spacing:1px;text-transform:uppercase;">Max</th>
                </tr>
            </thead>
            <tbody>{rows_html}</tbody>
        </table>
    </div>
    """, unsafe_allow_html=True)

    # Biểu đồ phân phối (histogram) cho 4 biến chính
    st.markdown('<p class="section-title" style="margin-top:8px;">📉 Phân phối dữ liệu các biến thời tiết</p>', unsafe_allow_html=True)
    hc1, hc2 = st.columns(2)
    hist_cfg = [
        ("temperature", "Nhiệt độ (°C)",   "#ff6b35", "rgba(255,107,53,0.15)"),
        ("humidity",    "Độ ẩm (%)",        "#42a5f5", "rgba(66,165,245,0.15)"),
        ("pressure",    "Áp suất (hPa)",    "#b388ff", "rgba(179,136,255,0.15)"),
        ("rainfall",    "Lượng mưa (mm)",   "#4fc3f7", "rgba(79,195,247,0.15)"),
    ]
    for idx, (col, label, color, fill) in enumerate(hist_cfg):
        fig_h = go.Figure()
        fig_h.add_trace(go.Histogram(
            x=df[col], nbinsx=25,
            marker=dict(color=color, line=dict(color=fill, width=0.5)),
            opacity=0.85, name=label,
        ))
        mean_val = df[col].mean()
        fig_h.add_vline(x=mean_val, line=dict(color="#e3b341", dash="dash", width=1.5),
                        annotation_text=f"Mean={mean_val:.1f}",
                        annotation_font_color="#e3b341",
                        annotation_font_size=11,
                        annotation_position="top right")
        lh2 = dict(PLOTLY_LAYOUT)
        lh2.update(
            height=230,
            showlegend=False,
            bargap=0.05,
            margin=dict(l=45, r=12, t=42, b=30),
            title=dict(
                text=label,
                font=dict(color="#e6edf3", size=13),
                x=0, xanchor="left", pad=dict(l=0, t=4)
            ),
            xaxis=dict(
                showgrid=False, zeroline=False,
                color="#8b949e", tickfont=dict(size=10)
            ),
            yaxis=dict(
                showgrid=True, gridcolor="#21262d", zeroline=False,
                tickfont=dict(size=10),
                title=dict(text="Tần suất", font=dict(size=10, color="#8b949e"))
            ),
        )
        fig_h.update_layout(**lh2)
        target_col = hc1 if idx % 2 == 0 else hc2
        with target_col:
            st.plotly_chart(fig_h, use_container_width=True, config={"displayModeBar": False})

# ── ROW GOLD — Phân tích từ Gold Layer ──
st.markdown("<hr class='g-divider'>", unsafe_allow_html=True)
with st.expander("📊 Phân tích dữ liệu theo giờ, tháng, năm", expanded=True):
    st.markdown('<p class="section-title">📊 Phân tích dữ liệu theo giờ, tháng, năm</p>', unsafe_allow_html=True)

    if "hour" not in df_gold.columns:
        df_gold["hour"]  = df_gold["time"].dt.hour
        df_gold["day"]   = df_gold["time"].dt.day
        df_gold["month"] = df_gold["time"].dt.month

    gc1, gc2, gc3 = st.columns(3)

    # ── Biểu đồ 1: Nhiệt độ trung bình theo GIỜ trong ngày ──
    with gc1:
        hourly_avg = df_gold.groupby("hour")["temperature"].mean().reset_index()
        fig_hour = go.Figure()
        fig_hour.add_trace(go.Bar(
            x=hourly_avg["hour"],
            y=hourly_avg["temperature"].round(1),
            marker=dict(
                color=hourly_avg["temperature"],
                colorscale=[[0,"#1a3a6b"],[0.5,"#ff6b35"],[1,"#f85149"]],
                showscale=False,
            ),
            text=[f"{v:.1f}°" for v in hourly_avg["temperature"]],
            textposition="outside", textfont=dict(size=9, color="#8b949e"),
        ))
        lg1 = dict(PLOTLY_LAYOUT)
        lg1.update(height=240, showlegend=False, bargap=0.1,
                   margin=dict(l=40, r=8, t=42, b=30),
                   title=dict(text="🕐 Nhiệt độ TB theo giờ trong ngày",
                              font=dict(color="#e6edf3", size=12), x=0, xanchor="left"),
                   xaxis=dict(showgrid=False, zeroline=False, color="#8b949e",
                              tickvals=list(range(0,24,3)),
                              ticktext=[f"{h}h" for h in range(0,24,3)],
                              tickfont=dict(size=10)),
                   yaxis=dict(showgrid=True, gridcolor="#21262d", zeroline=False,
                              tickfont=dict(size=10),
                              title=dict(text="°C", font=dict(size=10, color="#8b949e"))))
        fig_hour.update_layout(**lg1)
        st.plotly_chart(fig_hour, use_container_width=True, config={"displayModeBar": False})

    # ── Biểu đồ 2: Nhiệt độ & Độ ẩm trung bình theo THÁNG ──
    with gc2:
        month_avg = df_gold.groupby("month").agg(
            temperature=("temperature","mean"),
            humidity=("humidity","mean")
        ).reset_index()
        month_labels = ["T1","T2","T3","T4","T5","T6","T7","T8","T9","T10","T11","T12"]
        fig_month = go.Figure()
        fig_month.add_trace(go.Scatter(
            x=month_avg["month"], y=month_avg["temperature"].round(1),
            mode="lines+markers", name="Nhiệt độ (°C)",
            line=dict(color="#ff6b35", width=2),
            marker=dict(size=6, color="#ff6b35"),
            yaxis="y1",
        ))
        fig_month.add_trace(go.Scatter(
            x=month_avg["month"], y=month_avg["humidity"].round(1),
            mode="lines+markers", name="Độ ẩm (%)",
            line=dict(color="#42a5f5", width=2, dash="dot"),
            marker=dict(size=6, color="#42a5f5"),
            yaxis="y2",
        ))
        lg2 = dict(PLOTLY_LAYOUT)
        lg2.update(height=240, bargap=0.1,
                   margin=dict(l=40, r=40, t=42, b=30),
                   title=dict(text="📅 Nhiệt độ & Độ ẩm theo tháng",
                              font=dict(color="#e6edf3", size=12), x=0, xanchor="left"),
                   legend=dict(orientation="h", y=1.15, x=0,
                               font=dict(size=10, color="#8b949e")),
                   xaxis=dict(showgrid=False, zeroline=False, color="#8b949e",
                              tickvals=list(range(1,13)),
                              ticktext=month_labels, tickfont=dict(size=10)),
                   yaxis=dict(showgrid=True, gridcolor="#21262d", zeroline=False,
                              tickfont=dict(size=10), title=dict(text="°C", font=dict(size=10, color="#ff6b35"))),
                   yaxis2=dict(overlaying="y", side="right", showgrid=False,
                               zeroline=False, tickfont=dict(size=10, color="#42a5f5"),
                               title=dict(text="%", font=dict(size=10, color="#42a5f5"))))
        fig_month.update_layout(**lg2)
        st.plotly_chart(fig_month, use_container_width=True, config={"displayModeBar": False})

    # ── Biểu đồ 3: Heatmap Giờ × Tháng (Nhiệt độ TB) ──
    with gc3:
        pivot = df_gold.groupby(["month","hour"])["temperature"].mean().reset_index()
        pivot_table = pivot.pivot(index="month", columns="hour", values="temperature")
        fig_heat = go.Figure(go.Heatmap(
            z=pivot_table.values,
            x=[f"{h}h" for h in pivot_table.columns],
            y=[f"T{m}" for m in pivot_table.index],
            colorscale=[[0,"#0d1b3e"],[0.4,"#1565c0"],[0.7,"#ff6b35"],[1,"#f85149"]],
            showscale=True,
            colorbar=dict(thickness=10, tickfont=dict(color="#8b949e", size=9),
                          bgcolor="rgba(0,0,0,0)", bordercolor="#30363d"),
        ))
        lg3 = dict(PLOTLY_LAYOUT)
        lg3.update(height=240,
                   margin=dict(l=40, r=40, t=42, b=30),
                   title=dict(text="🌡️ Heatmap Nhiệt độ: Giờ × Tháng",
                              font=dict(color="#e6edf3", size=12), x=0, xanchor="left"),
                   xaxis=dict(color="#8b949e", tickfont=dict(size=9),
                              tickvals=[f"{h}h" for h in range(0,24,4)]),
                   yaxis=dict(color="#8b949e", tickfont=dict(size=9), showgrid=False))
        fig_heat.update_layout(**lg3)
        st.plotly_chart(fig_heat, use_container_width=True, config={"displayModeBar": False})

    # Ghi chú nguồn Gold
    st.markdown(
        '<div style="font-size:11px;color:#484f58;text-align:right;margin-top:-8px;">'
        '📦 Nguồn: <b style="color:#e3b341;">Gold Layer</b> — '
        'gold/year=2023/hanoi_weather_features.parquet · Feature Engineering bởi 2_etl.py'
        '</div>',
        unsafe_allow_html=True
    )

# ── Footer ──
st.markdown(f"""
<div style="text-align:center;padding:20px 0 8px;font-size:12px;color:#484f58;">
    🌤️ Weather Dashboard &nbsp;·&nbsp; Nguồn: MinIO Station — Hà Nội 2023 &nbsp;·&nbsp;
    {datetime.now().strftime("%H:%M:%S %d/%m/%Y")} &nbsp;·&nbsp; Streamlit + Plotly
</div>
""", unsafe_allow_html=True)
