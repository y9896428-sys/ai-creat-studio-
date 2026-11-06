import json
import os
from typing import Any

import replicate
import streamlit as st

# ---------------------------------------------------------
# إعداد الصفحة
# ---------------------------------------------------------
st.set_page_config(
    page_title="AI Creative Studio",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------
# تصميم الواجهة
# ---------------------------------------------------------
st.markdown(
    """
    <style>
    :root {
        --bg: #090a0d;
        --panel: #17191f;
        --panel2: #20232b;
        --line: #30343d;
        --muted: #a4a9b4;
        --text: #f5f6f8;
        --accent: #8173ff;
    }
    html, body, [data-testid="stAppViewContainer"] {
        background: var(--bg) !important;
        color: var(--text) !important;
    }
    [data-testid="stHeader"] { background: transparent !important; }
    [data-testid="stSidebar"] { display: none; }
    .block-container {
        max-width: 1600px;
        padding-top: 1rem;
        padding-bottom: 2rem;
    }
    h1, h2, h3, p, label, span { color: var(--text); }
    .top-title {
        font-size: 1.45rem;
        font-weight: 750;
        letter-spacing: .2px;
        margin: .25rem 0 1rem 0;
    }
    .subtle { color: var(--muted) !important; font-size: .88rem; }
    div[data-testid="stButton"] button,
    div[data-testid="stFormSubmitButton"] button {
        border-radius: 12px !important;
        border: 1px solid var(--line) !important;
        background: var(--panel2) !important;
        color: var(--text) !important;
        min-height: 2.7rem;
        font-weight: 600;
    }
    div[data-testid="stFormSubmitButton"] button[kind="primary"],
    div[data-testid="stButton"] button[kind="primary"] {
        background: #f0f1f5 !important;
        color: #111318 !important;
        border: 0 !important;
    }
    div[data-baseweb="select"] > div,
    div[data-testid="stTextArea"] textarea,
    div[data-testid="stTextInput"] input {
        background: #171a20 !important;
        color: #f5f6f8 !important;
        border-color: #353943 !important;
        border-radius: 12px !important;
    }
    div[data-testid="stTextArea"] textarea::placeholder {
        color: #9298a4 !important;
    }
    div[data-testid="stImage"] img,
    div[data-testid="stVideo"] video {
        border-radius: 13px;
    }
    .gallery-empty {
        border: 1px dashed #3b3f49;
        border-radius: 16px;
        padding: 2.2rem 1rem;
        text-align: center;
        color: #a4a9b4;
        background: #111318;
    }
    .composer {
        background: #171a20;
        border: 1px solid #3a3e48;
        border-radius: 18px;
        padding: 1rem;
        margin-top: 1rem;
    }
    div[data-testid="stHorizontalBlock"] { gap: .65rem; }
    [data-testid="stCaptionContainer"] p { color: var(--muted) !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------
# مفاتيح الاتصال: تحفظ في Streamlit Secrets ولا تظهر للمستخدم
# ---------------------------------------------------------
def get_secret(name: str, default: str = "") -> str:
    try:
        value = st.secrets.get(name, default)
        return str(value) if value is not None else default
    except Exception:
        return os.getenv(name, default)


API_TOKEN = get_secret("REPLICATE_API_TOKEN")
IMAGE_MODEL = get_secret("REPLICATE_IMAGE_MODEL")
VIDEO_MODEL = get_secret("REPLICATE_VIDEO_MODEL")

# إعدادات اختيارية خاصة بمدخلات كل موديل.
# اتركيها غير موجودة لاستخدام prompt فقط، أو ضعي JSON المتوافق
# مع صفحة الموديل في Streamlit Secrets.
IMAGE_INPUTS_JSON = get_secret(
    "IMAGE_INPUTS_JSON", '{"prompt": "{{PROMPT}}"}'
)
VIDEO_INPUTS_JSON = get_secret(
    "VIDEO_INPUTS_JSON", '{"prompt": "{{PROMPT}}"}'
)

client = replicate.Client(api_token=API_TOKEN) if API_TOKEN else None

# ---------------------------------------------------------
# وظائف مساعدة
# ---------------------------------------------------------
def build_inputs(raw_json: str, prompt: str, extra: dict | None = None) -> dict:
    try:
        inputs = json.loads(raw_json or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError(f"إعدادات الموديل غير صحيحة: {exc}") from exc

    if not isinstance(inputs, dict):
        raise ValueError("إعدادات الموديل يجب أن تكون JSON object.")

    def replace(value: Any) -> Any:
        if isinstance(value, str):
            return (
                value.replace("{{PROMPT}}", prompt)
                .replace("{{DURATION}}", str((extra or {}).get("duration", "")))
                .replace("{{ASPECT_RATIO}}", str((extra or {}).get("aspect_ratio", "")))
                .replace("{{RESOLUTION}}", str((extra or {}).get("resolution", "")))
            )
        if isinstance(value, list):
            return [replace(item) for item in value]
        if isinstance(value, dict):
            return {key: replace(item) for key, item in value.items()}
        return value

    inputs = replace(inputs)
    inputs.setdefault("prompt", prompt)
    return inputs


def collect_urls(result: Any) -> list[str]:
    urls: list[str] = []
    if isinstance(result, str):
        if result.startswith(("https://", "http://")):
            urls.append(result)
    elif isinstance(result, (list, tuple)):
        for item in result:
            urls.extend(collect_urls(item))
    elif isinstance(result, dict):
        for item in result.values():
            urls.extend(collect_urls(item))
    else:
        url = getattr(result, "url", None)
        if callable(url):
            try:
                url = url()
            except Exception:
                url = None
        if url:
            urls.append(str(url))
    return list(dict.fromkeys(urls))


def run_generation(model: str, inputs: dict) -> Any:
    if not API_TOKEN or client is None:
        raise RuntimeError(
            "إعداد الاتصال غير مكتمل. أضيفي REPLICATE_API_TOKEN في Streamlit Secrets."
        )
    if not model:
        raise RuntimeError(
            "لم يتم إعداد موديل هذا النوع بعد. أضيفي معرّف الموديل في Streamlit Secrets."
        )
    return client.run(model, input=inputs)


# حفظ عناصر المعرض خلال جلسة Streamlit الحالية
if "gallery_items" not in st.session_state:
    st.session_state.gallery_items = []

# ---------------------------------------------------------
# رأس الصفحة والفلاتر
# ---------------------------------------------------------
st.markdown('<div class="top-title">✦ AI CREATIVE STUDIO</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="subtle">Your creative space for images, videos and workflows.</div>',
    unsafe_allow_html=True,
)

filter_col, sort_col, refresh_col = st.columns([3, 1.2, 1])
with filter_col:
    gallery_filter = st.radio(
        "عرض المعرض",
        ["All", "Video", "Image"],
        horizontal=True,
        label_visibility="collapsed",
    )
with sort_col:
    sort_order = st.selectbox(
        "الترتيب", ["Newest", "Oldest"], label_visibility="collapsed"
    )
with refresh_col:
    st.button("↻ Refresh", use_container_width=True)

st.markdown("---")
items = list(st.session_state.gallery_items)
if sort_order == "Oldest":
    items.reverse()
if gallery_filter != "All":
    items = [item for item in items if item["type"] == gallery_filter.lower()]

if not items:
    st.markdown(
        """
        <div class="gallery-empty">
            <div style="font-size:2rem;">✦</div>
            <b>Your creations will appear here</b>
            <p style="color:#a4a9b4;margin-bottom:0;">
                ابدئي بإنشاء صورة أو فيديو، وستظهر النتيجة في هذا المعرض.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    cols_per_row = 4
    for start in range(0, len(items), cols_per_row):
        row_items = items[start : start + cols_per_row]
        cols = st.columns(cols_per_row)
        for col, item in zip(cols, row_items):
            with col:
                st.caption(item["type"].upper())
                if item["type"] == "image":
                    st.image(item["url"], use_container_width=True)
                else:
                    st.video(item["url"])
                st.caption(item.get("prompt", "")[:90])

# ---------------------------------------------------------
# لوحة الإنشاء
# ---------------------------------------------------------
st.markdown("---")
st.markdown("### Create something new")

mode = st.radio(
    "نوع الإنشاء",
    ["Image", "Video", "Workflow"],
    horizontal=True,
    label_visibility="collapsed",
)

if mode == "Workflow":
    st.info(
        "مساحة Workflow قيد التجهيز. سنضيف فيها ربط الصورة بالصوت والفيديو "
        "بعد التأكد من عمل توليد الصور والفيديو."
    )

elif mode == "Image":
    with st.form("image_generation_form"):
        prompt = st.text_area(
            "وصف الصورة",
            placeholder="Describe the image you want to create...",
            height=105,
        )
        c1, c2, c3 = st.columns(3)
        with c1:
            style = st.selectbox(
                "Style",
                ["Cinematic", "Photorealistic", "3D", "Anime", "Cartoon", "Artistic"],
            )
        with c2:
            aspect = st.selectbox("Aspect ratio", ["1:1", "16:9", "9:16", "4:5", "3:2"])
        with c3:
            quality = st.selectbox("Quality", ["Standard", "High", "Ultra"])

        submitted = st.form_submit_button(
            "✨ Generate image", type="primary", use_container_width=True
        )

    if submitted:
        if not prompt.strip():
            st.warning("اكتبي وصف الصورة أولًا.")
        else:
            final_prompt = (
                f"{prompt.strip()}. Visual style: {style}. "
                f"Aspect ratio requested: {aspect}. Quality preference: {quality}."
            )
            try:
                inputs = build_inputs(IMAGE_INPUTS_JSON, final_prompt)
                with st.spinner("Generating image..."):
                    result = run_generation(IMAGE_MODEL, inputs)
                urls = collect_urls(result)
                if not urls:
                    st.success("انتهى الطلب، لكن الموديل لم يُرجع رابط صورة واضحًا.")
                    st.write(str(result))
                else:
                    for url in urls:
                        st.session_state.gallery_items.insert(
                            0, {"type": "image", "url": url, "prompt": prompt.strip()}
                        )
                    st.success("تم إنشاء الصورة بنجاح.")
                    st.image(urls[0], use_container_width=True)
                    st.markdown(f"[فتح الصورة]({urls[0]})")
            except Exception as exc:
                st.error(f"تعذر إنشاء الصورة: {exc}")

elif mode == "Video":
    with st.form("video_generation_form"):
        prompt = st.text_area(
            "وصف الفيديو والحركة",
            placeholder="Describe the scene, action, camera movement and mood...",
            height=105,
        )
        c1, c2, c3 = st.columns(3)
        with c1:
            aspect = st.selectbox("Aspect ratio", ["16:9", "9:16", "1:1"])
        with c2:
            duration = st.selectbox("Duration", ["5s", "8s", "10s"])
        with c3:
            resolution = st.selectbox("Resolution", ["720p", "1080p"])

        submitted = st.form_submit_button(
            "🎬 Generate video", type="primary", use_container_width=True
        )

    if submitted:
        if not prompt.strip():
            st.warning("اكتبي وصف الفيديو أولًا.")
        else:
            final_prompt = (
                f"{prompt.strip()}. Requested duration: {duration}. "
                f"Aspect ratio: {aspect}. Requested resolution: {resolution}."
            )
            extra = {
                "duration": duration.replace("s", ""),
                "aspect_ratio": aspect,
                "resolution": resolution,
            }
            try:
                inputs = build_inputs(VIDEO_INPUTS_JSON, final_prompt, extra)
                with st.spinner("Generating video... قد يستغرق الأمر بعض الوقت."):
                    result = run_generation(VIDEO_MODEL, inputs)
                urls = collect_urls(result)
                if not urls:
                    st.success("انتهى الطلب، لكن الموديل لم يُرجع رابط فيديو واضحًا.")
                    st.write(str(result))
                else:
                    for url in urls:
                        st.session_state.gallery_items.insert(
                            0, {"type": "video", "url": url, "prompt": prompt.strip()}
                        )
                    st.success("تم إنشاء الفيديو بنجاح.")
                    st.video(urls[0])
                    st.markdown(f"[فتح الفيديو]({urls[0]})")
            except Exception as exc:
                st.error(f"تعذر إنشاء الفيديو: {exc}")

st.markdown(
    '<p class="subtle" style="text-align:center;margin-top:2rem;">'
    'AI Creative Studio · Powered by Replicate</p>',
    unsafe_allow_html=True,
)
