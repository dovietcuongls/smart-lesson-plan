import streamlit as st
import google.generativeai as genai
import PyPDF2
import docx
import os
from dotenv import load_dotenv

# Tải biến môi trường từ file .env (nếu có)
load_dotenv()

# Cấu hình giao diện Streamlit
st.set_page_config(page_title="Trợ lý Phân tích Văn bản", page_icon="📝", layout="wide")

st.title("📝 Trợ lý Phân tích Văn bản & Lập Kế hoạch")
st.markdown("""
Ứng dụng này sử dụng **Gemini AI** làm trợ lý đắc lực để đọc hiểu văn bản của bạn. 
Mỗi khi bạn tải lên một tài liệu, hệ thống sẽ tự động tóm tắt nội dung chính và trích xuất một danh sách các công việc cụ thể (to-do list) để bạn dễ dàng theo dõi và thực hiện.
""")

# Thanh bên (Sidebar) để cấu hình API Key
with st.sidebar:
    st.header("⚙️ Cấu hình Hệ thống")
    api_key_input = st.text_input("Nhập Google Gemini API Key:", type="password", value=os.getenv("GEMINI_API_KEY", ""))
    st.markdown("[Lấy API Key miễn phí tại Google AI Studio](https://aistudio.google.com/app/apikey)")
    st.markdown("---")
    st.markdown("""
    **Hỗ trợ các định dạng:**
    - Text (`.txt`)
    - PDF (`.pdf`)
    - Word (`.docx`)
    """)
    selected_model_name = "gemini-1.5-flash"
    if api_key_input:
        genai.configure(api_key=api_key_input)
        try:
            available_models = []
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    available_models.append(m.name)
            
            if available_models:
                default_index = 0
                for i, m_name in enumerate(available_models):
                    if "1.5-flash" in m_name:
                        default_index = i
                        break
                st.markdown("---")
                selected_model_name = st.selectbox("🤖 Chọn mô hình AI:", available_models, index=default_index)
            else:
                st.warning("⚠️ Không tìm thấy mô hình nào hỗ trợ tạo nội dung với API Key này.")
        except Exception as e:
            st.error(f"Lỗi khi lấy danh sách mô hình: {e}")

# Hàm đọc nội dung từ file PDF
def extract_text_from_pdf(file):
    pdf_reader = PyPDF2.PdfReader(file)
    text = ""
    for page in pdf_reader.pages:
        extracted = page.extract_text()
        if extracted:
            text += extracted + "\n"
    return text

# Hàm đọc nội dung từ file Word
def extract_text_from_docx(file):
    doc = docx.Document(file)
    return "\n".join([para.text for para in doc.paragraphs])

# Mẫu Promt chuẩn hóa cho Gemini
PROMPT_TEMPLATE = """
Bạn là một trợ lý AI thông minh, chuyên nghiệp và có khả năng phân tích yêu cầu xuất sắc.
Dưới đây là nội dung của một văn bản mà người dùng đã tải lên:

---
{text}
---

Dựa vào nội dung văn bản trên, hãy thực hiện 2 nhiệm vụ sau một cách chính xác và rõ ràng:

1. **Tóm tắt nội dung chính (Executive Summary)**:
   - Viết một đoạn tóm tắt ngắn gọn (khoảng 3-5 câu) nêu bật những thông điệp, mục tiêu hoặc quyết định quan trọng nhất của văn bản.

2. **Kế hoạch hành động cụ thể (Actionable To-Do List)**:
   - Liệt kê các công việc CỤ THỂ cần làm để hoàn thành tốt các yêu cầu/nhiệm vụ được nêu trong văn bản.
   - Trình bày dưới dạng danh sách checklist (có thể sử dụng gạch đầu dòng hoặc hộp kiểm).
   - Nếu có các mốc thời gian hoặc người phụ trách (nếu được nhắc đến trong văn bản), hãy ghi chú rõ.
   - Đảm bảo các hành động được mô tả theo dạng động từ chỉ hành động (Ví dụ: "Liên hệ...", "Chuẩn bị...", "Gửi...").

Hãy phân tích kỹ và trả lời bằng Tiếng Việt, sử dụng định dạng Markdown đẹp, chuyên nghiệp để dễ đọc.
"""

# Khu vực upload file
uploaded_file = st.file_uploader("Kéo thả hoặc dấn để tải văn bản lên", type=["txt", "pdf", "docx"])

if uploaded_file is not None:
    if not api_key_input:
        st.error("⚠️ Vui lòng nhập Gemini API Key ở thanh công cụ bên trái trước khi phân tích.")
    else:
        st.info("Đã nhận file. Đang tiến hành đọc và phân tích...")
        
        text_content = ""
        try:
            # Xử lý file dựa trên loại định dạng
            if uploaded_file.name.endswith(".txt"):
                text_content = uploaded_file.read().decode("utf-8")
            elif uploaded_file.name.endswith(".pdf"):
                text_content = extract_text_from_pdf(uploaded_file)
            elif uploaded_file.name.endswith(".docx"):
                text_content = extract_text_from_docx(uploaded_file)
            
            # Kiểm tra xem file có nội dung text hợp lệ hay không
            if not text_content.strip():
                st.warning("Tài liệu của bạn không chứa văn bản (có thể là ảnh quét) hoặc bị trống. Vui lòng thử file khác.")
            else:
                st.success("Đã trích xuất nội dung văn bản thành công! Đang gọi Gemini AI phân tích...")
                
                # Tạo dải phân cách giao diện
                st.divider()
                
                # Chia layout: Bên trái hiển thị 1 phần text gốc (tùy chọn), bên phải hiển thị kết quả
                col1, col2 = st.columns([1, 2])
                
                with col1:
                    st.subheader("📄 Giới thiệu tài liệu")
                    st.write(f"**Tên file:** {uploaded_file.name}")
                    st.write(f"**Độ dài:** ~{len(text_content.split())} từ")
                    with st.expander("Xem nội dung gốc (đã trích xuất)"):
                        st.text(text_content)
                
                with col2:
                    st.subheader("✨ Phân tích từ Gemini AI")
                    with st.spinner("Gemini đang đọc và lên kế hoạch... Vui lòng đợi trong giây lát."):
                        try:
                            # Khởi tạo model AI đã được chọn từ thanh bên
                            model = genai.GenerativeModel(selected_model_name)
                            
                            # Gửi prompt chuyên biệt
                            prompt = PROMPT_TEMPLATE.format(text=text_content)
                            response = model.generate_content(prompt)
                            
                            # Hiển thị kết quả
                            st.markdown(response.text)
                            
                        except Exception as e:
                            st.error(f"❌ Đã xảy ra lỗi khi giao tiếp với Gemini API: {str(e)}")
                            
        except Exception as e:
            st.error(f"❌ Lỗi khi đọc file: {str(e)}")
