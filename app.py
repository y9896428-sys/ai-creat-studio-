import json
import os
import tempfile
from pathlib import Path

import replicate
import streamlit as st

st.set_page_config(
    page_title="استوديو الإبداع بالذكاء الاصطناعي",
    page_icon="🎬",
    layout="wide",
)

st.title("🎬 استوديو الإبداع بالذكاء الاصطناعي")
st.caption("إنشاء الصور والفيديوهات والقصص — عبر نماذج تختارها من Replicate.")

# قراءة الرمز من Streamlit Secrets أو متغير البيئة.
try:
    API_TOKEN = st.secrets.get("REPLICATE_API_TOKEN", "")
except Exception:
    API_TOKEN = ""

API_TOKEN = API_TOKEN or os.getenv("REPLICATE_API_TOKEN", "")

with st.sidebar:
    st.header("⚙️ إعدادات الاتصال")
    st.write("أضف رمز Replicate في إعدادات التطبيق أو في ملف `.env`/متغيرات البيئة.")
    st.caption("لا تضع رمز API مباشرة داخل الكود أو في مستودع عام.")

if not API_TOKEN:
    st.warning(
        "لم يتم العثور على REPLICATE_API_TOKEN. أضف الرمز قبل استخدام التوليد."
    )

client = replicate.Client(api_token=API_TOKEN) if API_TOKEN else None

def build_inputs(raw_json: str, prompt: str) -> dict:
    """يقرأ JSON خاصًا بمدخلات النموذج ويستبدل {{PROMPT}} بالنص."""
    try:
        inputs = json.loads(raw_json or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON غير صالح: {exc}") from exc

    if not isinstance(inputs, dict):
        raise ValueError("يجب أن تكون مدخلات النموذج كائن JSON.")

    def replace_prompt(value):
        if isinstance(value, str):
            return value.replace("{{PROMPT}}", prompt)
        if isinstance(value, list):
            return [replace_prompt(item) for item in value]
        if isinstance(value, dict):
            return {key: replace_prompt(item) for key, item in value.items()}
        return value

    inputs = replace_prompt(inputs)
    inputs.setdefault("prompt", prompt)
    return inputs

def output_to_text(value) -> str:
    """تحويل ناتج النموذج إلى نص قابل للعرض."""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return "\n".join(output_to_text(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, indent=2)
    return str(value)

def output_urls(value) -> list[str]:
    """استخراج روابط الملفات من نواتج Replicate الشائعة."""
    urls = []

    if isinstance(value, str):
        if value.startswith(("https://", "http://")):
            urls.append(value)
    elif isinstance(value, (list, tuple)):
        for item in value:
            urls.extend(output_urls(item))
    elif isinstance(value, dict):
        for item in value.values():
            urls.extend(output_urls(item))
    else:
        url = getattr(value, "url", None)
        if url:
            urls.append(str(url))
        else:
            text = str(value)
            if text.startswith(("https://", "http://")):
                urls.append(text)

    return list(dict.fromkeys(urls))

def run_model(model_name: str, inputs: dict):
    if not API_TOKEN or client is None:
        raise RuntimeError("أضف REPLICATE_API_TOKEN أولًا.")
    if not model_name.strip():
        raise ValueError("أدخل معرّف النموذج، مثل owner/model.")
    return client.run(model_name.strip(), input=inputs)

def show_download(url: str, filename: str):
    st.markdown(f"[فتح الملف أو تنزيله]({url})")
    try:
        import requests

        response = requests.get(url, timeout=60)
        response.raise_for_status()
        st.download_button(
            "⬇️ تنزيل",
            data=response.content,
            file_name=filename,
            mime=response.headers.get("content-type", "application/octet-stream"),
            key=f"download-{filename}-{url}",
        )
    except Exception:
        st.caption("تعذّر تجهيز زر التنزيل المباشر؛ استخدم رابط الملف أعلاه.")

tab_images, tab_videos, tab_stories = st.tabs(
    ["📸 الصور", "🎥 الفيديوهات", "📖 القصص والترجمة"]
)

# ---------------- الصور ----------------
with tab_images:
    st.header("توليد الصور")
    with st.form("image_form"):
        image_prompt = st.text_area(
            "وصف الصورة",
            placeholder="مثال: شخصية كرتونية لطيفة على شكل جزرة في حديقة...",
            height=110,
        )

        col1, col2, col3 = st.columns(3)
        with col1:
            image_style = st.selectbox(
                "النمط", ["أنمي", "كرتوني", "3D", "سينمائي", "واقعي", "شخصيات خضروات"]
            )
        with col2:
            image_count = st.slider("عدد النتائج المطلوب", 1, 6, 1)
        with col3:
            image_quality = st.selectbox("الجودة المطلوبة", ["1080p HD", "4K", "8K"])

        image_model = st.text_input(
            "معرّف نموذج الصور على Replicate",
            value=os.getenv("REPLICATE_IMAGE_MODEL", ""),
            placeholder="owner/model",
        )
        image_inputs_json = st.text_area(
            "مدخلات إضافية للنموذج بصيغة JSON",
            value='{"prompt": "{{PROMPT}}"}',
        )
        image_submit = st.form_submit_button("✨ توليد الصور", type="primary")

    if image_submit:
        if not image_prompt.strip():
            st.warning("أدخل وصف الصورة أولًا.")
        else:
            final_prompt = (
                f"{image_prompt.strip()}. النمط: {image_style}. "
                f"الجودة المطلوبة: {image_quality}. "
                f"عدد النتائج المطلوب: {image_count}."
            )
            try:
                inputs = build_inputs(image_inputs_json, final_prompt)
                with st.spinner("جارٍ إرسال الطلب وانتظار نتيجة نموذج الصور..."):
                    result = run_model(image_model, inputs)

                urls = output_urls(result)
                if urls:
                    st.success("اكتمل توليد الصور.")
                    cols = st.columns(min(len(urls), 3))
                    for index, url in enumerate(urls):
                        with cols[index % len(cols)]:
                            st.image(url, caption=f"النتيجة {index + 1}")
                            show_download(url, f"image-{index + 1}.png")
                else:
                    st.success("اكتمل الطلب.")
                    st.write(output_to_text(result))
            except Exception as exc:
                st.error(f"تعذّر توليد الصور: {exc}")

# ---------------- الفيديوهات ----------------
with tab_videos:
    st.header("توليد الفيديوهات")
    with st.form("video_form"):
        video_prompt = st.text_area(
            "سيناريو أو وصف الفيديو",
            placeholder="صف الأحداث والشخصيات والمكان وحركة الكاميرا...",
            height=120,
        )

        col1, col2, col3 = st.columns(3)
        with col1:
            duration = st.selectbox(
                "المدة المطلوبة",
                ["دقيقة واحدة", "دقيقتان", "5 دقائق", "10 دقائق", "15 دقيقة"],
            )
        with col2:
            video_style = st.selectbox(
                "النمط", ["3D", "سينمائي", "أنمي", "كرتوني", "واقعي"]
            )
        with col3:
            camera_mode = st.selectbox(
                "الكاميرا",
                ["تلقائي", "لقطة واسعة", "لقطة قريبة", "كاميرا متحركة"],
            )

        character_count = st.number_input(
            "عدد الشخصيات", min_value=1, max_value=10, value=1
        )
        characters = [
            st.text_input(f"وصف الشخصية {index + 1}", key=f"video-character-{index}")
            for index in range(int(character_count))
        ]
        sync_audio = st.checkbox("طلب مزامنة الصوت وحركة الشفاه", value=False)

        video_model = st.text_input(
            "معرّف نموذج الفيديو على Replicate",
            value=os.getenv("REPLICATE_VIDEO_MODEL", "tencent/hunyuan-video"),
            placeholder="owner/model",
        )
        video_inputs_json = st.text_area(
            "مدخلات إضافية للنموذج بصيغة JSON",
            value='{"prompt": "{{PROMPT}}"}',
        )
        video_submit = st.form_submit_button("🎬 توليد الفيديو", type="primary")

    if video_submit:
        if not video_prompt.strip():
            st.warning("أدخل وصف الفيديو أولًا.")
        else:
            character_text = "، ".join(item.strip() for item in characters if item.strip())
            final_prompt = (
                f"{video_prompt.strip()}. المدة المطلوبة: {duration}. "
                f"النمط: {video_style}. الكاميرا: {camera_mode}. "
                f"الشخصيات: {character_text or 'غير محددة'}. "
                f"مزامنة الصوت وحركة الشفاه: {'مطلوبة' if sync_audio else 'غير مطلوبة'}."
            )
            try:
                inputs = build_inputs(video_inputs_json, final_prompt)
                with st.spinner("جارٍ إرسال الطلب وانتظار نتيجة نموذج الفيديو..."):
                    result = run_model(video_model, inputs)

                urls = output_urls(result)
                if urls:
                    st.success("اكتمل توليد الفيديو.")
                    for index, url in enumerate(urls):
                        st.video(url)
                        show_download(url, f"video-{index + 1}.mp4")
                else:
                    st.success("اكتمل الطلب.")
                    st.write(output_to_text(result))
            except Exception as exc:
                st.error(f"تعذّر توليد الفيديو: {exc}")

# ---------------- القصص ----------------
with tab_stories:
    st.header("إنشاء القصص والسيناريوهات")
    story_mode = st.radio(
        "طريقة إنشاء القصة",
        ["من فكرة نصية", "من صورة"],
        horizontal=True,
    )

    with st.form("story_form"):
        uploaded_image = None
        if story_mode == "من فكرة نصية":
            story_prompt = st.text_area(
                "فكرة القصة",
                placeholder="مثال: طفل يعثر على خريطة سرية في مكتبة قديمة...",
                height=120,
            )
        else:
            uploaded_image = st.file_uploader(
                "ارفع صورة",
                type=["png", "jpg", "jpeg", "webp"],
            )
            story_prompt = st.text_area(
                "تعليمات إضافية للقصة (اختياري)",
                placeholder="اكتب نوع القصة أو الشخصيات أو الأحداث المطلوبة...",
                height=90,
            )

        story_language = st.selectbox(
            "لغة النتيجة", ["العربية", "English", "العربية والإنجليزية"]
        )
        story_model = st.text_input(
            "معرّف نموذج القصة على Replicate",
            value=os.getenv("REPLICATE_STORY_MODEL", ""),
            placeholder="owner/model",
        )
        story_inputs_json = st.text_area(
            "مدخلات النموذج بصيغة JSON",
            value='{"prompt": "{{PROMPT}}"}',
        )

        image_input_key = st.text_input(
            "اسم حقل الصورة في النموذج",
            value="image",
        )
        story_submit = st.form_submit_button("📖 إنشاء القصة", type="primary")

    if story_submit:
        if story_mode == "من فكرة نصية" and not story_prompt.strip():
            st.warning("أدخل فكرة القصة أولًا.")
        elif story_mode == "من صورة" and uploaded_image is None:
            st.warning("ارفع صورة أولًا.")
        else:
            final_prompt = (
                f"{story_prompt.strip() or 'أنشئ قصة مناسبة للصورة.'} "
                f"اكتب النتيجة باللغة: {story_language}. "
                "نظّمها إلى عنوان، قصة، ثم مشاهد عند ملاءمة ذلك."
            )
            try:
                inputs = build_inputs(story_inputs_json, final_prompt)

                if uploaded_image is not None:
                    suffix = Path(uploaded_image.name).suffix or ".png"
                    with tempfile.NamedTemporaryFile(
                        suffix=suffix, delete=False
                    ) as temp_file:
                        temp_file.write(uploaded_image.getvalue())
                        temp_path = temp_file.name

                    try:
                        with open(temp_path, "rb") as image_file:
                            inputs[image_input_key.strip() or "image"] = image_file
                            with st.spinner("جارٍ تحليل الصورة وإنشاء القصة..."):
                                result = run_model(story_model, inputs)
                    finally:
                        Path(temp_path).unlink(missing_ok=True)
                else:
                    with st.spinner("جارٍ إنشاء القصة..."):
                        result = run_model(story_model, inputs)

                st.success("اكتمل إنشاء القصة.")
                st.markdown(output_to_text(result))
            except Exception as exc:
                st.error(f"تعذّر إنشاء القصة: {exc}")
