import streamlit as st
import google.generativeai as genai
import PyPDF2
import docx
from PIL import Image
import pandas as pd
import io
import os
import re

# ==========================================
# CẤU HÌNH BACKEND: Khai báo API Key ở đây
# ==========================================
# Bạn hãy thay thế chuỗi bên dưới bằng API Key thật của bạn.
# Tuyệt đối không để lộ mã này lên GitHub công khai.
GOOGLE_API_KEY = "PASTE_YOUR_API_KEY_HERE"

# Ưu tiên cấu hình từ Streamlit Secrets, nếu không có thì lấy trực tiếp từ biến trên
try:
    API_KEY = st.secrets.get("GEMINI_API_KEY", GOOGLE_API_KEY)
except Exception:
    API_KEY = GOOGLE_API_KEY

def configure_genai():
    if API_KEY and API_KEY != "PASTE_YOUR_API_KEY_HERE":
        genai.configure(api_key=API_KEY)
        return True
    return False

# ==========================================
# THIẾT LẬP GIAO DIỆN (UI)
# ==========================================
st.set_page_config(page_title="Trợ lý Xử lý Văn bản Chỉ đạo", page_icon="📝", layout="wide")

# Áp dụng Custom CSS cho tông màu Xanh đậm - Trắng và Footer
st.markdown("""
    <style>
    /* Chỉnh màu chữ tiêu đề chính */
    .stApp {
        background-color: #FFFFFF;
    }
    h1, h2, h3 {
        color: #003366 !important; /* Xanh dương đậm */
    }
    /* Tùy chỉnh Sidebar */
    [data-testid="stSidebar"] {
        background-color: #F0F4F8;
    }
    /* Chỉnh sửa layout Markdown Table cho đẹp */
    table {
        width: 100%;
        border-collapse: collapse;
    }
    th {
        background-color: #004080;
        color: white;
        text-align: left;
        padding: 8px;
    }
    td {
        border: 1px solid #ddd;
        padding: 8px;
    }
    tr:nth-child(even) {
        background-color: #f2f2f2;
    }
    /* Footer */
    .footer {
        position: fixed;
        left: 0;
        bottom: 0;
        width: 100%;
        background-color: transparent;
        color: gray;
        text-align: center;
        padding: 10px;
        font-size: 14px;
        z-index: 100;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🏛️ Trợ lý Xử lý Văn bản Chỉ đạo")
st.markdown("**Số hóa quy trình bóc tách công việc từ văn bản nhà nước/nhà trường một cách tự động và chính xác.**")
st.divider()

# ==========================================
# CÁC HÀM XỬ LÝ ĐỌC FILE
# ==========================================
def extract_text_from_pdf(file):
    text = ""
    try:
        pdf_reader = PyPDF2.PdfReader(file)
        for page in pdf_reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
    except Exception as e:
        raise Exception(f"Không thể đọc file PDF (có thể là file scan hoặc bị lỗi): {e}")
    return text

def extract_text_from_docx(file):
    try:
        doc = docx.Document(file)
        return "\n".join([para.text for para in doc.paragraphs])
    except Exception as e:
        raise Exception(f"Không thể đọc file Word: {e}")

# Hàm chuyển đổi Markdown Table sang DataFrame của Pandas
def markdown_table_to_df(markdown_str):
    # Tìm tất cả các dòng chứa ký tự '|' báo hiệu bảng
    lines = markdown_str.strip().split('\n')
    table_lines = [line for line in lines if '|' in line]
    
    if not table_lines:
        return None
        
    # Xử lý tiêu đề (dòng đầu tiên)
    header_line = table_lines[0]
    headers = [col.strip() for col in header_line.split('|') if col.strip()]
    
    # Xử lý các dòng dữ liệu (bỏ qua dòng phân cách ---|--- thường là dòng số 2)
    data = []
    for line in table_lines[1:]:
        # Bỏ qua dòng format ----
        if set(line.replace('|', '').replace('-', '').replace(' ', '').replace(':', '')) == set():
            continue
        cols = [col.strip() for col in line.split('|')[1:-1]] # Bỏ cột rỗng ở đầu và cuối do split
        if len(cols) == len(headers):
            data.append(cols)
        elif len(cols) > 0: # Cố gắng điền nếu độ dài không khớp do xuống dòng markdown
            # Cắt hoặc padding thêm
            if len(cols) > len(headers):
                cols = cols[:len(headers)]
            else:
                cols = cols + [""] * (len(headers) - len(cols))
            data.append(cols)
            
    if headers and data:
        return pd.DataFrame(data, columns=headers)
    return None

# ==========================================
# SIDEBAR
# ==========================================
with st.sidebar:
    st.header("📂 Tải Văn Bản")
    uploaded_file = st.file_uploader(
        "Kéo thả hoặc dán file vào đây", 
        type=["pdf", "docx", "png", "jpg", "jpeg"]
    )
    
    st.markdown("---")
    st.markdown("""
    **✅ Hướng dẫn sử dụng:**
    1. Tải lên công văn, kế hoạch (File Word, PDF) hoặc ảnh chụp công văn có dấu đỏ.
    2. Đợi hệ thống AI đọc và xử lý.
    3. Nhận bảng công việc đã được bóc tách tự động.
    4. Tải file Excel về máy để lưu minh chứng theo dõi.
    """)

# ==========================================
# XỬ LÝ CHÍNH
# ==========================================

PROMPT_TEXT = """Đóng vai một Hiệu trưởng / Quản lý hành chính trường học. Hãy đọc văn bản chỉ đạo sau và bóc tách thông tin thành một bảng nghiêm ngặt. 
Bảng phải gồm chính xác 4 cột:
1. Tóm tắt Nội dung chính (Ngắn gọn 2-3 câu).
2. Đối tượng thực hiện (Ghi đích danh: GV Ngữ văn, Lịch sử, Ban giám hiệu, Bảo vệ...).
3. Hành động cần làm (Liệt kê gạch đầu dòng các công việc cụ thể).
4. Hạn hoàn thành (Rút trích ngày tháng, nếu văn bản không ghi thì điền 'Theo tiến độ chung').
Trả về kết quả 100% dưới dạng Markdown Table để tôi hiển thị lên web.
"""

if uploaded_file is not None:
    if not configure_genai():
        st.error("⚠️ LỖI: Chưa cấu hình GOOGLE_API_KEY ở backend. Vui lòng kiểm tra mã nguồn (app.py) hoặc cấu hình Streamlit Secrets.")
    else:
        st.info(f"Đang phân tích tài liệu: **{uploaded_file.name}**...")
        
        file_ext = uploaded_file.name.split('.')[-1].lower()
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        try:
            with st.spinner("AI đang bóc tách dự liệu... Vui lòng đợi trong giây lát."):
                response = None
                
                # Xử lý ảnh (Gửi thẳng file ảnh qua Vision model)
                if file_ext in ['png', 'jpg', 'jpeg']:
                    image = Image.open(uploaded_file)
                    st.image(image, caption="Ảnh chụp công văn tải lên", width=300)
                    response = model.generate_content([PROMPT_TEXT, image])
                    
                # Xử lý text từ PDF hoặc DOCX
                else:
                    text_content = ""
                    if file_ext == "pdf":
                        text_content = extract_text_from_pdf(uploaded_file)
                    elif file_ext == "docx":
                        text_content = extract_text_from_docx(uploaded_file)
                    
                    if not text_content.strip():
                        st.warning("⚠️ Không tìm thấy chữ trong văn bản. Nếu đây là PDF dạng scan (văn bản chụp hình), vui lòng chuyển sang file ảnh (.png, .jpg) để upload lại.")
                    else:
                        full_prompt = PROMPT_TEXT + "\\n\\nNội dung văn bản:\\n" + text_content
                        response = model.generate_content(full_prompt)
                
                # Render kết quả
                if response:
                    st.success("✅ Đã bóc tách thành công!")
                    
                    st.subheader("📊 Bảng Phân công Công việc")
                    markdown_result = response.text
                    
                    # Hiện bảng lên màn hình
                    st.markdown(markdown_result)
                    
                    # Xử lý xuất Excel
                    df = markdown_table_to_df(markdown_result)
                    if df is not None:
                        # Ghi Dataframe ra bộ nhớ đệm (buffer) để tạo file Excel tải xuống
                        output = io.BytesIO()
                        with pd.ExcelWriter(output, engine='openpyxl') as writer:
                            df.to_excel(writer, index=False, sheet_name='Phan_Cong')
                        
                        excel_data = output.getvalue()
                        
                        st.markdown("---")
                        col1, col2, col3 = st.columns([1, 2, 1])
                        with col2:
                            st.download_button(
                                label="📥 Tải xuống Bảng Phân công (Excel)",
                                data=excel_data,
                                file_name=f"Ban_Phan_Cong_{uploaded_file.name}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                use_container_width=True
                            )
                    else:
                        st.warning("⚠️ AI trả về kết quả nhưng không nằm trong định dạng bảng chuẩn nên không thể tạo file Excel. Xin thử lại với tư duy khác của AI.")
                        
        except Exception as e:
            st.error(f"❌ Xảy ra lỗi trong quá trình xử lý: {str(e)}")


# ==========================================
# FOOTER
# ==========================================
st.markdown('<div class="footer">© 2026 Bản quyền thuộc về Đỗ Viết Cường - Trường PTDTNT Cao Lộc</div>', unsafe_allow_html=True)
