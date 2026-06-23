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
        if len(cols) > 0:
            # Cắt hoặc padding thêm nếu số cột không khớp
            if len(cols) > len(headers):
                cols = cols[:len(headers)]
            elif len(cols) < len(headers):
                cols = cols + [""] * (len(headers) - len(cols))
            
            # Cấu hình xuống dòng thực thụ cho Excel
            cols = [col.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n") for col in cols]
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
# GIAO DIỆN CHÍNH (TABS)
# ==========================================
tab1, tab2 = st.tabs(["Quản lý nội trú", "Phòng thí nghiệm văn học"])

# ------------------------------------------
# TAB 1: QUẢN LÝ NỘI TRÚ (Xử lý văn bản chỉ đạo)
# ------------------------------------------
with tab1:
    st.title("🏛️ Trợ lý Xử lý Văn bản Chỉ đạo")
    st.markdown("**Số hóa quy trình bóc tách công việc từ văn bản nhà nước/nhà trường một cách tự động và chính xác.**")
    st.divider()

    PROMPT_TEXT = """Đóng vai một Hiệu trưởng / Quản lý hành chính trường học. Hãy đọc văn bản chỉ đạo sau và bóc tách thông tin thành một bảng nghiêm ngặt. 
Bảng phải gồm chính xác 4 cột:
1. Tóm tắt Nội dung chính (Ngắn gọn 2-3 câu).
2. Đối tượng thực hiện (Ghi đích danh: GV Ngữ văn, Lịch sử, Ban giám hiệu, Bảo vệ...).
3. Hành động cần làm (Liệt kê gạch đầu dòng các công việc cụ thể. BẮT BUỘC dùng thẻ HTML <br> để xuống dòng giữa các gạch đầu dòng để giao diện hiển thị đẹp mắt).
4. Hạn hoàn thành (Rút trích ngày tháng, nếu văn bản không ghi thì điền 'Theo tiến độ chung').
Trả về kết quả 100% dưới dạng Markdown Table để tôi hiển thị lên web.
"""

    if uploaded_file is not None:
        if not configure_genai():
            st.error("⚠️ LỖI: Chưa cấu hình GOOGLE_API_KEY ở backend. Vui lòng kiểm tra mã nguồn (app.py) hoặc cấu hình Streamlit Secrets.")
        else:
            st.info(f"Đang phân tích tài liệu: **{uploaded_file.name}**...")
            
            try:
                # Lấy danh sách model khả dụng
                available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                if not available_models:
                    raise Exception("API Key của bạn không có quyền truy cập vào bất kỳ mô hình Gemini nào hỗ trợ tạo nội dung.")
                    
                # Ưu tiên chọn gemini-1.5-flash hoặc gemini-2.5-flash nếu có, nếu không thì lấy model đầu tiên
                selected_model = available_models[0]
                for m_name in available_models:
                    if "1.5-flash" in m_name or "2.5-flash" in m_name:
                        selected_model = m_name
                        break
                        
                model = genai.GenerativeModel(selected_model)
                
                with st.spinner(f"AI ({selected_model}) đang bóc tách dữ liệu... Vui lòng đợi trong giây lát."):
                    response = None
                    
                    file_ext = uploaded_file.name.split('.')[-1].lower()
                    
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
                        
                        # Hiện bảng lên màn hình và cho phép render thẻ HTML <br>
                        st.markdown(markdown_result, unsafe_allow_html=True)
                        
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

# ------------------------------------------
# TAB 2: PHÒNG THÍ NGHIỆM VĂN HỌC (Trò chơi kéo thả âm thanh tương tác)
# ------------------------------------------
with tab2:
    st.title("🧪 Phòng Thí Nghiệm Văn Học")
    st.markdown("**Trò chơi học tập: Kéo thả lắp ráp hoàn thiện cấu trúc sơ đồ tư duy Nghị luận xã hội tư tưởng đạo lý.**")
    st.divider()
    
    # Khởi tạo trạng thái phiên làm việc (Session State) cho tab Phòng thí nghiệm văn học
    if "literature_json" not in st.session_state:
        st.session_state.literature_json = None
    if "current_literature_topic" not in st.session_state:
        st.session_state.current_literature_topic = ""
        
    topic_input = st.text_input("Nhập chủ đề nghị luận xã hội tư tưởng đạo lý:", placeholder="Ví dụ: Lòng dũng cảm, Sự chia sẻ, Tự lập...")
    
    # Nếu người dùng thay đổi chủ đề mới, tự động xóa kết quả cũ để tránh nhầm lẫn
    if topic_input != st.session_state.current_literature_topic:
        st.session_state.current_literature_topic = topic_input
        st.session_state.literature_json = None
        
    start_btn = st.button("BẮT ĐẦU THÍ NGHIỆM")
    
    if start_btn:
        if not topic_input.strip():
            st.warning("⚠️ Vui lòng nhập chủ đề nghị luận xã hội tư tưởng đạo lý!")
        else:
            if not configure_genai():
                st.error("⚠️ LỖI: Chưa cấu hình GOOGLE_API_KEY ở backend. Vui lòng kiểm tra mã nguồn (app.py) hoặc cấu hình Streamlit Secrets.")
            else:
                with st.spinner("Gemini đang thiết lập sơ đồ liên kết và chuẩn bị các hạt thử thách..."):
                    try:
                        # Lấy danh sách model khả dụng
                        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                        if not available_models:
                            raise Exception("API Key của bạn không có quyền truy cập vào bất kỳ mô hình Gemini nào hỗ trợ tạo nội dung.")
                            
                        # Ưu tiên chọn gemini-1.5-flash hoặc gemini-2.5-flash nếu có
                        selected_model = available_models[0]
                        for m_name in available_models:
                            if "1.5-flash" in m_name or "2.5-flash" in m_name:
                                selected_model = m_name
                                break
                        
                        model = genai.GenerativeModel(selected_model)
                        
                        system_instruction = (
                            "Bạn là một chuyên gia giảng dạy Ngữ văn THPT độc đáo và sáng tạo. Nhiệm vụ của bạn là phân tích chủ đề nghị luận xã hội về tư tưởng đạo lý được cung cấp và thiết kế một cấu trúc sơ đồ tư duy mạng lưới các hạt tương tác liên kết (dưới dạng JSON chứa 'nodes' và 'links').\\n\\n"
                            "Cấu trúc sơ đồ tư duy bắt buộc phải tuân theo cấu trúc bài nghị luận xã hội chuẩn như sau:\\n"
                            "1. Luận đề (Core Theme): Là hạt trung tâm (nhóm 'luan_de'), kích thước lớn (size: 100-110), lực (luc): 0.0.\\n"
                            "2. Các luận điểm lớn của bài viết (nhóm 'luan_diem', size: 85-90), bao gồm:\\n"
                            "   - Mở bài (Mở bài: Đặt vấn đề, luc: -0.2)\\n"
                            "   - Giải thích (Thân bài: Giải thích ý nghĩa, luc: -0.1)\\n"
                            "   - Phân tích & Chứng minh (Thân bài: Phân tích & Chứng minh, luc: 0.2)\\n"
                            "   - Bàn luận mở rộng (Thân bài: Bàn luận mở rộng, luc: 0.1)\\n"
                            "   - Bài học (Thân bài: Bài học bản thân, luc: -0.3)\\n"
                            "   - Kết bài (Kết bài: Thông điệp gửi gắm, luc: -0.2)\\n"
                            "   Tất cả các hạt luận điểm lớn này phải có liên kết trực tiếp (links) với hạt Luận đề trung tâm.\\n"
                            "3. Các hạt chi tiết, dẫn chứng, hành động (nhóm 'chi_tiet', size: 70-80), liên kết với hạt luận điểm lớn tương ứng của nó:\\n"
                            "   - Mở bài liên kết với các hạt: Dẫn dắt, Trích dẫn/Khái niệm, Khái quát ý nghĩa.\\n"
                            "   - Giải thích liên kết với các hạt: Nghĩa đen/nghĩa bóng, Ý nghĩa cốt lõi.\\n"
                            "   - Phân tích & Chứng minh liên kết với các hạt: Lý do vì sao cần tư tưởng này?, Dẫn chứng thực tế 1 (ghi rõ tên tấm gương nổi tiếng cụ thể), Dẫn chứng thực tế 2 (tấm gương tiêu biểu khác).\\n"
                            "   - Bàn luận mở rộng liên kết với các hạt: Phê phán lối sống ích kỷ/trái đạo lý, Mở rộng góc nhìn thời đại.\\n"
                            "   - Bài học liên kết với các hạt: Nhận thức đúng đắn, Hành động cụ thể áp dụng.\\n"
                            "   - Kết bài liên kết với các hạt: Khẳng định giá trị, Liên hệ bản thân.\\n\\n"
                            "4. Các hạt tung hỏa mù (Decoys - nhóm 'hoa_mu', size: 75-80, luc: 0.0, mau: '#64748B'):\\n"
                            "   Hãy sinh thêm từ 2 đến 3 hạt mang tư tưởng tiêu cực, ngụy biến, lệch lạc hoặc hành vi trái ngược hoàn toàn với tinh thần chủ đề (Ví dụ: với chủ đề 'Lòng dũng cảm' thì sinh các hạt hỏa mù như 'Hèn nhát trốn tránh', 'Liều lĩnh mù quáng', 'Thờ ơ ích kỷ').\\n"
                            "   LƯU Ý CỰC KỲ QUAN TRỌNG: Không khai báo bất kỳ liên kết (links) nào cho các hạt hỏa mù này trong mảng 'links'. Chúng đứng độc lập.\\n\\n"
                            "VẬT LÝ HẠT (Thuộc tính 'luc'):\\n"
                            "- Các hạt mang tính chất thực tiễn, cụ thể, dẫn chứng phải có lực dương (luc: từ 1.5 đến 3.5) để chúng trĩu nặng xuống dưới.\\n"
                            "- Các hạt mang tính chất khát vọng, bài học, hành động vươn lên, lý thuyết khái quát phải có lực âm (luc: từ -3.5 đến -1.5) để chúng bay nhẹ lên trên.\\n"
                            "- Các hạt trung lập hoặc trung tâm có lực gần bằng 0 (-0.5 đến 0.5) để tự cân bằng ở giữa.\\n\\n"
                            "BẢNG MÀU SẮC (Mã màu HEX 'mau'):\\n"
                            "- Luận đề: Màu đặc biệt nổi bật (ví dụ: Đỏ đậm #DC2626 hoặc Xanh tối #1E3A8A).\\n"
                            "- Luận điểm chính: Các tông màu trung tính sang trọng (ví dụ: Xanh dương #3B82F6, Xanh ngọc #0D9488, Tím #7C3AED).\\n"
                            "- Chi tiết & Dẫn chứng nặng: Màu ấm (ví dụ: Cam #F97316, Đỏ cam #EA580C) để dễ nhận diện ở đáy.\\n"
                            "- Bài học & Hành động nhẹ: Màu mát (ví dụ: Xanh lá sáng #10B981, Xanh chuối #84CC16) để bay lên trên.\\n\\n"
                            "YÊU CẦU ĐỊNH DẠNG TRẢ VỀ:\\n"
                            "- Chỉ trả về chuỗi JSON chuẩn chứa hai mảng 'nodes' và 'links', không chứa bất kỳ lời dẫn giải thích hay markdown nào khác ngoài JSON.\\n"
                            "- Mỗi node có cấu trúc: {\\\"id\\\": số, \\\"ten\\\": \\\"chuỗi ngắn 2-5 từ\\\", \\\"nhom\\\": \\\"nhóm\\\", \\\"luc\\\": số thực, \\\"mau\\\": \\\"mã HEX\\\", \\\"size\\\": số nguyên}\\n"
                            "- Mỗi link có cấu trúc: {\\\"source\\\": id_nguon, \\\"target\\\": id_dich}\\n"
                        )
                        
                        prompt = f"{system_instruction}\\n\\nChủ đề: {topic_input}"
                        
                        response = model.generate_content(prompt)
                        response_text = response.text.strip()
                        
                        # Làm sạch chuỗi JSON nếu Gemini trả về kèm theo markdown
                        if "```json" in response_text:
                            response_text = response_text.split("```json")[1].split("```")[0].strip()
                        elif "```" in response_text:
                            response_text = response_text.split("```")[1].split("```")[0].strip()
                            
                        import json
                        parsed_data = json.loads(response_text)
                        
                        if isinstance(parsed_data, dict) and "nodes" in parsed_data and "links" in parsed_data:
                            st.session_state.literature_json = parsed_data
                            st.success("✅ Đã chuẩn bị phòng thí nghiệm! Hãy sẵn sàng thử thách.")
                        else:
                            st.error("❌ Dữ liệu trả về không đúng định dạng mạng lưới. Vui lòng thử lại.")
                    except Exception as e:
                        st.error(f"❌ Lỗi xử lý từ Gemini: {str(e)}")
                        
    if st.session_state.literature_json:
        st.subheader("🧩 Trò chơi ghép nối sơ đồ lập luận xã hội")
        st.markdown(
            "🎮 **LUẬT CHƠI & HƯỚNG DẪN:**\\n"
            "1. **Phía bên trái** là các ô tròn nét đứt (slots) gợi ý các phần của bài văn.\\n"
            "2. **Phía bên phải** là các hạt luận điểm, dẫn chứng và **hạt tung hỏa mù (decoy)** nằm lộn xộn.\\n"
            "3. Sử dụng ngón tay chạm vuốt (Smartphone) hoặc chuột kéo thả (PC) đưa các hạt từ bên phải lắp vào đúng vị trí bên trái. **Nếu xếp đúng hạt, đường kết nối sẽ tự động phát sáng hiện ra**.\\n"
            "4. Các hạt hỏa mù (nội dung lệch lạc/sai) không có ô trống nào bên trái, hãy để chúng bay tự do bên phải.\\n"
            "5. Sau khi ghép xong, hãy nhấn nút **ĐÃ HOÀN THÀNH** ở góc dưới bên phải để kiểm tra. Nếu xếp sai/thiếu, **hệ thống sẽ rung chuyển và nổ văng các hạt chưa snap về bên phải**! Nếu xếp đúng, **luồng sáng tư duy sẽ chạy mượt mà từ Mở bài đến Kết bài**!"
        )
        
        # Chuyển đổi dữ liệu JSON sang chuỗi an toàn
        import json
        literature_data_str = json.dumps(st.session_state.literature_json, ensure_ascii=False)
        
        # Mã HTML nhúng p5.js với trò chơi ghép nối và hiệu ứng nổ tung/luồng sáng
        p5_canvas_html = f"""
        <!DOCTYPE html>
        <html lang="vi">
        <head>
          <meta charset="UTF-8">
          <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
          <script src="https://cdnjs.cloudflare.com/ajax/libs/p5.js/1.4.0/p5.js"></script>
          <style>
            body {{
              margin: 0;
              padding: 0;
              overflow: hidden;
              background-color: #F8FAFC;
              user-select: none;
              -webkit-user-select: none;
              touch-action: none;
            }}
            #canvas-container {{
              width: 100%;
              height: 550px;
              display: block;
              position: relative;
            }}
          </style>
        </head>
        <body>
          <div id="canvas-container"></div>
          <script>
            const particleData = {literature_data_str};
            let particles = [];
            let links = [];
            let draggedParticle = null;
            let offsetX = 0;
            let offsetY = 0;
            
            // Cấu hình responsive
            let col1, col2, col3, scaleFactor, startX;
            const outlineGroups = ['mo_bai', 'giai_thich', 'phan_tich_chung_minh', 'ban_luan_mo_rong', 'bai_hoc', 'ket_bai'];
            
            // Các biến trạng thái game/hiệu ứng
            let flashFrames = 0;
            let shakeFrames = 0;
            let showExplosionText = false;
            let showSuccessText = false;
            let explosionTimer = 0;
            let successTimer = 0;
            
            // Trạng thái chạy luồng sáng khi thắng cuộc
            let flowActive = false;
            let flowStep = 0;
            let flowProgress = 0.0;
            let seq = [];
            let childNodesMap = {{}};
            
            // Web Audio API Click/Snap Sound Synthesizer
            let audioCtx = null;
            
            function playClickSound() {{
              try {{
                if (!audioCtx) {{
                  audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                }}
                if (audioCtx.state === 'suspended') {{
                  audioCtx.resume();
                }}
                let osc = audioCtx.createOscillator();
                let gainNode = audioCtx.createGain();
                osc.connect(gainNode);
                gainNode.connect(audioCtx.destination);
                
                osc.type = 'sine';
                osc.frequency.setValueAtTime(1000, audioCtx.currentTime);
                osc.frequency.exponentialRampToValueAtTime(150, audioCtx.currentTime + 0.04);
                
                gainNode.gain.setValueAtTime(0.2, audioCtx.currentTime);
                gainNode.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.04);
                
                osc.start();
                osc.stop(audioCtx.currentTime + 0.05);
              }} catch (e) {{
                console.log("Audio Context Error: ", e);
              }}
            }}
            
            function playSnapSound() {{
              try {{
                if (!audioCtx) {{
                  audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                }}
                if (audioCtx.state === 'suspended') {{
                  audioCtx.resume();
                }}
                let osc = audioCtx.createOscillator();
                let gainNode = audioCtx.createGain();
                osc.connect(gainNode);
                gainNode.connect(audioCtx.destination);
                
                osc.type = 'triangle';
                osc.frequency.setValueAtTime(550, audioCtx.currentTime);
                osc.frequency.exponentialRampToValueAtTime(260, audioCtx.currentTime + 0.08);
                
                gainNode.gain.setValueAtTime(0.35, audioCtx.currentTime);
                gainNode.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.09);
                
                osc.start();
                osc.stop(audioCtx.currentTime + 0.1);
              }} catch (e) {{
                console.log(e);
              }}
            }}
            
            function playExplosionSound() {{
              try {{
                if (!audioCtx) {{
                  audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                }}
                if (audioCtx.state === 'suspended') {{
                  audioCtx.resume();
                }}
                
                let bufferSize = audioCtx.sampleRate * 0.45;
                let buffer = audioCtx.createBuffer(1, bufferSize, audioCtx.sampleRate);
                let data = buffer.getChannelData(0);
                for (let i = 0; i < bufferSize; i++) {{
                  data[i] = Math.random() * 2 - 1;
                }}
                
                let noise = audioCtx.createBufferSource();
                noise.buffer = buffer;
                
                let filter = audioCtx.createBiquadFilter();
                filter.type = 'lowpass';
                filter.frequency.setValueAtTime(700, audioCtx.currentTime);
                filter.frequency.exponentialRampToValueAtTime(60, audioCtx.currentTime + 0.35);
                
                let gain = audioCtx.createGain();
                gain.gain.setValueAtTime(0.5, audioCtx.currentTime);
                gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.4);
                
                noise.connect(filter);
                filter.connect(gain);
                gain.connect(audioCtx.destination);
                
                noise.start();
              }} catch (e) {{
                console.log(e);
              }}
            }}
            
            function playSuccessSound() {{
              try {{
                if (!audioCtx) {{
                  audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                }}
                if (audioCtx.state === 'suspended') {{
                  audioCtx.resume();
                }}
                
                // Arpeggio Major Chord C5 - E5 - G5 - C6
                let chord = [523.25, 659.25, 783.99, 1046.50];
                chord.forEach((freq, idx) => {{
                  let osc = audioCtx.createOscillator();
                  let gain = audioCtx.createGain();
                  osc.connect(gain);
                  gain.connect(audioCtx.destination);
                  
                  osc.type = 'sine';
                  osc.frequency.setValueAtTime(freq, audioCtx.currentTime + idx * 0.08);
                  
                  gain.gain.setValueAtTime(0.0, audioCtx.currentTime + idx * 0.08);
                  gain.gain.linearRampToValueAtTime(0.25, audioCtx.currentTime + idx * 0.08 + 0.02);
                  gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + idx * 0.08 + 0.22);
                  
                  osc.start(audioCtx.currentTime + idx * 0.08);
                  osc.stop(audioCtx.currentTime + idx * 0.08 + 0.28);
                }});
              }} catch (e) {{
                console.log(e);
              }}
            }}
            
            // Hàm chuẩn hóa chuỗi phân loại nhóm của Gemini thành chuẩn của game
            function getGroupType(nhom) {{
              if (!nhom) return 'chi_tiet';
              let n = nhom.toLowerCase().normalize("NFD").replace(/[\\u0300-\\u036f]/g, "").replace(/\\s+/g, "_");
              if (n.includes('luan_de') || n.includes('chu_de') || n.includes('trung_tam')) return 'luan_de';
              if (n.includes('mo_bai') || n.includes('nhap_de') || n.includes('dat_van_de') || n.includes('mo_dau')) return 'mo_bai';
              if (n.includes('giai_thich')) return 'giai_thich';
              if (n.includes('phan_tich') || n.includes('chung_minh')) return 'phan_tich_chung_minh';
              if (n.includes('ban_luan') || n.includes('mo_rong') || n.includes('danh_gia') || n.includes('ban_bac')) return 'ban_luan_mo_rong';
              if (n.includes('bai_hoc') || n.includes('hanh_dong') || n.includes('nhan_thuc')) return 'bai_hoc';
              if (n.includes('ket_bai') || n.includes('ket_luan') || n.includes('thong_diep') || n.includes('vi_lien_he')) return 'ket_bai';
              if (n.includes('hoa_mu') || n.includes('nguy_bien') || n.includes('nham') || n.includes('decoy')) return 'hoa_mu';
              return 'chi_tiet';
            }}
            
            function calculateLayout() {{
              // Tự động thu nhỏ hạt trên màn hình nhỏ để tránh tràn màn hình di động
              scaleFactor = windowWidth < 600 ? 0.68 : 1.0;
              
              if (windowWidth > 800) {{
                col1 = windowWidth * 0.07;
                col2 = windowWidth * 0.22;
                col3 = windowWidth * 0.38;
                startX = windowWidth * 0.52;
              }} else if (windowWidth > 500) {{
                col1 = 60;
                col2 = 160;
                col3 = 260;
                startX = 330;
              }} else {{
                col1 = 35;
                col2 = 105;
                col3 = 175;
                startX = 225;
              }}
            }}
            
            function setup() {{
              let canvas = createCanvas(windowWidth, 550);
              canvas.parent('canvas-container');
              
              calculateLayout();
              
              let nodes = particleData.nodes || [];
              links = particleData.links || [];
              
              // 1. Khởi tạo hạt với chuỗi chuẩn hóa nhóm hạt
              for (let i = 0; i < nodes.length; i++) {{
                let data = nodes[i];
                let pSize = parseInt(data.size) || 80;
                let gType = getGroupType(data.nhom);
                
                particles.push({{
                  id: Number(data.id),
                  ten: data.ten,
                  nhom: data.nhom,
                  nhomType: gType,
                  luc: parseFloat(data.luc) || 0,
                  mau: data.mau || '#3B82F6',
                  origSize: pSize,
                  radius: (pSize / 2) * scaleFactor,
                  x: 0,
                  y: 0,
                  vx: 0,
                  vy: 0,
                  isSnapped: false,
                  isStatic: false,
                  tx: null,
                  ty: null
                }});
              }}
              
              // 2. Định nghĩa vị trí đích (Targets) dựa trên loại hạt đã chuẩn hóa
              assignTargets();
              
              // 3. Phân bổ vị trí khởi tạo: Luận đề nằm tĩnh bên trái, còn lại lộn xộn bên phải
              let rootNode = particles.find(p => p.nhomType === 'luan_de');
              for (let p of particles) {{
                if (rootNode && p.id === rootNode.id) {{
                  p.x = p.tx;
                  p.y = p.ty;
                }} else {{
                  // Đặt lộn xộn bên phải
                  p.x = random(startX + p.radius, windowWidth - p.radius);
                  p.y = random(40, 500);
                }}
              }}
              
              // 4. Thiết lập chuỗi các nút luận điểm phục vụ hoạt động chạy luồng sáng
              if (rootNode) {{
                seq.push(rootNode);
              }}
              
              let outlineNodes = particles.filter(p => outlineGroups.includes(p.nhomType));
              outlineNodes.sort((a, b) => outlineGroups.indexOf(a.nhomType) - outlineGroups.indexOf(b.nhomType));
              seq = seq.concat(outlineNodes);
            }}
            
            function assignTargets() {{
              let rootNode = particles.find(p => p.nhomType === 'luan_de');
              let outlineNodes = particles.filter(p => outlineGroups.includes(p.nhomType));
              outlineNodes.sort((a, b) => outlineGroups.indexOf(a.nhomType) - outlineGroups.indexOf(b.nhomType));
              
              childNodesMap = {{}};
              for (let outline of outlineNodes) {{
                let children = [];
                for (let link of links) {{
                  let sId = Number(link.source);
                  let tId = Number(link.target);
                  let oId = Number(outline.id);
                  
                  if (sId === oId) {{
                    let targetNode = particles.find(p => p.id === tId && p.nhomType === 'chi_tiet');
                    if (targetNode) children.push(targetNode);
                  }} else if (tId === oId) {{
                    let sourceNode = particles.find(p => p.id === sId && p.nhomType === 'chi_tiet');
                    if (sourceNode) children.push(sourceNode);
                  }}
                }}
                childNodesMap[outline.id] = children;
              }}
              
              // Khớp vị trí Luận đề
              if (rootNode) {{
                rootNode.tx = col1;
                rootNode.ty = 275;
                rootNode.isSnapped = true;
                rootNode.isStatic = true;
              }}
              
              // Khớp vị trí 6 luận điểm lớn
              let outlineYSpacing = [50, 140, 230, 320, 410, 500];
              for (let i = 0; i < outlineNodes.length; i++) {{
                let node = outlineNodes[i];
                node.tx = col2;
                node.ty = outlineYSpacing[i];
              }}
              
              // Khớp vị trí các hạt chi tiết nhánh của từng luận điểm
              for (let i = 0; i < outlineNodes.length; i++) {{
                let outline = outlineNodes[i];
                let oy = outlineYSpacing[i];
                let children = childNodesMap[outline.id] || [];
                
                if (children.length === 1) {{
                  let p = children[0];
                  p.tx = col3; p.ty = oy;
                }} else if (children.length === 2) {{
                  let p1 = children[0];
                  let p2 = children[1];
                  if (p1) {{ p1.tx = col3; p1.ty = oy - 25 * scaleFactor; }}
                  if (p2) {{ p2.tx = col3; p2.ty = oy + 25 * scaleFactor; }}
                }} else if (children.length >= 3) {{
                  let p1 = children[0];
                  let p2 = children[1];
                  let p3 = children[2];
                  if (p1) {{ p1.tx = col3; p1.ty = oy - 35 * scaleFactor; }}
                  if (p2) {{ p2.tx = col3; p2.ty = oy; }}
                  if (p3) {{ p3.tx = col3; p3.ty = oy + 35 * scaleFactor; }}
                }}
              }}
            }}
            
            function draw() {{
              // Hiệu ứng Rung lắc (Camera Shake) khi nổ
              if (shakeFrames > 0) {{
                push();
                translate(random(-6, 6), random(-6, 6));
                shakeFrames--;
              }}
              
              background('#F1F5F9');
              
              // 1. Vẽ các ô chứa mục tiêu (Slots) ở bên trái làm đích kéo thả
              for (let i = 0; i < particles.length; i++) {{
                let p = particles[i];
                if (p.tx !== null && !p.isStatic) {{
                  stroke('#94A3B8');
                  strokeWeight(1.5);
                  drawingContext.setLineDash([4, 6]); // Nét đứt mờ
                  noFill();
                  ellipse(p.tx, p.ty, p.radius * 2);
                  drawingContext.setLineDash([]); // Tắt nét đứt
                  
                  // Chỉ hiển thị nhãn gợi ý khi hạt chưa lắp ráp đúng chỗ
                  if (!p.isSnapped) {{
                    noStroke();
                    fill('#94A3B8');
                    textSize(10 * scaleFactor);
                    textAlign(CENTER, CENTER);
                    
                    let label = "";
                    if (p.nhomType === 'mo_bai') label = "Mở bài";
                    else if (p.nhomType === 'giai_thich') label = "Giải thích";
                    else if (p.nhomType === 'phan_tich_chung_minh') label = "Chứng minh";
                    else if (p.nhomType === 'ban_luan_mo_rong') label = "Bàn luận";
                    else if (p.nhomType === 'bai_hoc') label = "Bài học";
                    else if (p.nhomType === 'ket_bai') label = "Kết bài";
                    else label = "Chi tiết";
                    
                    text(label, p.tx, p.ty);
                  }}
                }}
              }}
              
              // 2. Vẽ đường nối (Links) - CHỈ hiển thị nếu hạt nguồn & hạt đích đều đã được snap chính xác
              stroke('#94A3B8');
              strokeWeight(1.8);
              for (let i = 0; i < links.length; i++) {{
                let link = links[i];
                let p1 = particles.find(p => p.id === Number(link.source));
                let p2 = particles.find(p => p.id === Number(link.target));
                if (p1 && p2) {{
                  if ((p1.isStatic || p1.isSnapped) && (p2.isStatic || p2.isSnapped)) {{
                    line(p1.x, p1.y, p2.x, p2.y);
                  }}
                }}
              }}
              
              // 3. Chạy hiệu ứng luồng sáng tư duy khi thắng cuộc
              if (flowActive) {{
                flowProgress += 0.022; // tốc độ di chuyển tia sáng
                if (flowProgress >= 1.0) {{
                  flowProgress = 0.0;
                  flowStep++;
                  if (flowStep >= seq.length - 1) {{
                    flowActive = false; // hoàn thành luồng
                  }}
                }}
                
                // Vẽ các đường nối phát sáng màu vàng cam
                stroke('#F59E0B');
                strokeWeight(4);
                
                for (let s = 0; s <= flowStep; s++) {{
                  let currentP = seq[s];
                  if (s < seq.length - 1 && s < flowStep) {{
                    let nextP = seq[s+1];
                    line(currentP.x, currentP.y, nextP.x, nextP.y);
                  }}
                  
                  // Đồng thời làm sáng các hạt chi tiết đã snap của luận điểm
                  let children = getChildren(currentP.id);
                  for (let child of children) {{
                    if (child.isSnapped) {{
                      line(currentP.x, currentP.y, child.x, child.y);
                    }}
                  }}
                }}
                
                // Vẽ xung sáng (pulse orb) đang di chuyển
                if (flowStep < seq.length - 1) {{
                  let nA = seq[flowStep];
                  let nB = seq[flowStep+1];
                  if (nA && nB) {{
                    let px = lerp(nA.x, nB.x, flowProgress);
                    let py = lerp(nA.y, nB.y, flowProgress);
                    line(nA.x, nA.y, px, py);
                    
                    fill('#F59E0B');
                    stroke('#FFFBEB');
                    strokeWeight(3);
                    ellipse(px, py, 22 * scaleFactor);
                  }}
                }}
              }}
              
              // 4. Cập nhật vật lý và va chạm cho các hạt
              for (let i = 0; i < particles.length; i++) {{
                let p = particles[i];
                
                if (p.isSnapped || p.isStatic) {{
                  // Đứng yên tuyệt đối nếu đã snap đúng vị trí
                  p.x = p.tx;
                  p.y = p.ty;
                  p.vx = 0;
                  p.vy = 0;
                }} else if (p !== draggedParticle) {{
                  // Hạt tự do nổi/chìm nhẹ
                  p.vy += p.luc * 0.04;
                  
                  // Lực đẩy giữ các hạt chưa snap ở phần bên phải (Messy Zone)
                  if (p.x < startX) {{
                    p.vx += (startX - p.x) * 0.06;
                  }}
                  
                  p.vx *= 0.92;
                  p.vy *= 0.92;
                  
                  p.x += p.vx;
                  p.y += p.vy;
                }}
                
                // Ranh giới canvas cho hạt tự do
                if (!p.isSnapped && !p.isStatic) {{
                  if (p.x < p.radius) {{ p.x = p.radius; p.vx *= -0.5; }}
                  if (p.x > width - p.radius) {{ p.x = width - p.radius; p.vx *= -0.5; }}
                  if (p.y < p.radius) {{ p.y = p.radius; p.vy *= -0.5; }}
                  if (p.y > height - p.radius) {{ p.y = height - p.radius; p.vy *= -0.5; }}
                }}
              }}
              
              // Tránh chồng chéo giữa các hạt tự do
              for (let i = 0; i < particles.length; i++) {{
                for (let j = i + 1; j < particles.length; j++) {{
                  let p1 = particles[i];
                  let p2 = particles[j];
                  if (!p1.isSnapped || !p2.isSnapped) {{
                    let d = dist(p1.x, p1.y, p2.x, p2.y);
                    let minDist = p1.radius + p2.radius + 8;
                    if (d < minDist) {{
                      let overlap = minDist - d;
                      let angle = atan2(p2.y - p1.y, p2.x - p1.x);
                      let forceX = cos(angle) * overlap * 0.18;
                      let forceY = sin(angle) * overlap * 0.18;
                      
                      if (!p1.isSnapped && !p1.isStatic && p1 !== draggedParticle) {{
                        p1.vx -= forceX;
                        p1.vy -= forceY;
                      }}
                      if (!p2.isSnapped && !p2.isStatic && p2 !== draggedParticle) {{
                        p2.vx += forceX;
                        p2.vy += forceY;
                      }}
                    }}
                  }}
                }}
              }}
              
              // 5. Vẽ các hạt tư duy
              for (let i = 0; i < particles.length; i++) {{
                let p = particles[i];
                
                if (p === draggedParticle) {{
                  fill('rgba(15, 23, 42, 0.15)');
                  noStroke();
                  ellipse(p.x + 3, p.y + 5, p.radius * 2 + 6);
                }}
                
                // Vẽ hạt chính (Hạt hỏa mù sẽ có màu xám #64748B)
                fill(p.mau);
                stroke('#FFFFFF');
                strokeWeight(3);
                ellipse(p.x, p.y, p.radius * 2);
                
                // Viết chữ trong hạt
                drawWrappedText(p.ten, p.x, p.y, p.radius);
              }}
              
              // 6. Vẽ nút bấm ĐÃ HOÀN THÀNH (Capsule Button)
              let btnW = 150 * scaleFactor;
              let btnH = 38 * scaleFactor;
              let btnX = width - btnW - 15;
              let btnY = height - btnH - 15;
              
              let isHover = (mouseX > btnX && mouseX < btnX + btnW && mouseY > btnY && mouseY < btnY + btnH);
              fill(isHover ? '#0F766E' : '#0D9488');
              noStroke();
              rect(btnX, btnY, btnW, btnH, 19 * scaleFactor);
              
              fill(255);
              textSize(12 * scaleFactor);
              textAlign(CENTER, CENTER);
              textStyle(BOLD);
              text("ĐÃ HOÀN THÀNH", btnX + btnW/2, btnY + btnH/2);
              
              // 7. Vẽ Flash chớp màn hình khi lỗi
              if (flashFrames > 0) {{
                fill(239, 68, 68, map(flashFrames, 0, 15, 0, 100)); // Đỏ chớp tắt
                noStroke();
                rect(0, 0, width, height);
                flashFrames--;
              }}
              
              if (shakeFrames >= 0) {{
                pop(); // Kết thúc dịch chuyển rung lắc camera
              }}
              
              // 8. Hiển thị thông báo trạng thái
              if (showExplosionText && explosionTimer > 0) {{
                fill('#DC2626');
                stroke('#FFFFFF');
                strokeWeight(4);
                textSize(20 * scaleFactor);
                textStyle(BOLD);
                textAlign(CENTER, CENTER);
                text("💥 SAI CẤU TRÚC / CHƯA XẾP XONG! HẠT ĐÃ NỔ TUNG! HÃY CHỌN LẠI! 💥", width / 2, height / 2);
                explosionTimer--;
                if (explosionTimer === 0) showExplosionText = false;
              }}
              
              if (showSuccessText && successTimer > 0) {{
                fill('#0D9488');
                stroke('#FFFFFF');
                strokeWeight(4);
                textSize(22 * scaleFactor);
                textStyle(BOLD);
                textAlign(CENTER, CENTER);
                text("🏆 CHÚC MỪNG! BẠN ĐÃ LẮP RÁP DÀN Ý CHUẨN XÁC! 🏆", width / 2, height / 2);
                successTimer--;
                if (successTimer === 0) showSuccessText = false;
              }}
            }}
            
            // Hàm vẽ tự động phân chia dòng văn bản cho vừa khít hạt tròn
            function drawWrappedText(txt, x, y, radius) {{
              fill('#FFFFFF');
              noStroke();
              textAlign(CENTER, CENTER);
              textSize(11 * scaleFactor);
              textStyle(BOLD);
              
              let words = txt.split(' ');
              let lines = [];
              let currentLine = words[0] || "";
              
              for (let i = 1; i < words.length; i++) {{
                let word = words[i];
                let w = textWidth(currentLine + " " + word);
                if (w < radius * 1.5) {{
                  currentLine += " " + word;
                }} else {{
                  lines.push(currentLine);
                  currentLine = word;
                }}
              }}
              if (currentLine) {{
                lines.push(currentLine);
              }}
              
              let lineHeight = 13 * scaleFactor;
              let startY = y - (lines.length - 1) * lineHeight / 2;
              for (let i = 0; i < lines.length; i++) {{
                text(lines[i], x, startY + i * lineHeight);
              }}
            }}
            
            // Logic kiểm định hoàn thành bài học
            function checkCompletion() {{
              let allSnapped = true;
              
              // Duyệt kiểm tra tất cả các hạt hợp lệ (có tx khác null) xem đã snap hết chưa
              for (let i = 0; i < particles.length; i++) {{
                let p = particles[i];
                if (p.tx !== null && !p.isStatic) {{
                  if (!p.isSnapped) {{
                    allSnapped = false;
                    break;
                  }}
                }}
              }}
              
              if (allSnapped) {{
                showSuccessText = true;
                successTimer = 220;
                flowActive = true;
                flowStep = 0;
                flowProgress = 0.0;
                showExplosionText = false;
                
                playSuccessSound(); // Nhạc chiến thắng!
              }} else {{
                // Kích hoạt hiệu ứng bùng nổ camera
                flashFrames = 15;
                shakeFrames = 25;
                showExplosionText = true;
                explosionTimer = 120;
                showSuccessText = false;
                flowActive = false;
                
                playExplosionSound(); // Tiếng nổ tung!
                
                // Thổi bay các hạt tự do (chưa snap / hạt hỏa mù) ngược về góc bên phải
                for (let i = 0; i < particles.length; i++) {{
                  let p = particles[i];
                  if (!p.isSnapped && !p.isStatic) {{
                    let angle = random(-PI/4, PI/4); // Thổi chéo về bên phải
                    let speed = random(14, 24);
                    p.vx = cos(angle) * speed;
                    p.vy = sin(angle) * speed;
                  }}
                }}
              }}
            }}
            
            function checkButtonClick(tX, tY) {{
              let btnW = 150 * scaleFactor;
              let btnH = 38 * scaleFactor;
              let btnX = width - btnW - 15;
              let btnY = height - btnH - 15;
              
              if (tX > btnX && tX < btnX + btnW && tY > btnY && tY < btnY + btnH) {{
                checkCompletion();
                return true;
              }}
              return false;
            }}
            
            // Khởi tạo hoạt động kéo thả
            function startDrag(tX, tY) {{
              for (let i = particles.length - 1; i >= 0; i--) {{
                let p = particles[i];
                let d = dist(tX, tY, p.x, p.y);
                if (d < p.radius) {{
                  if (p.isStatic) break; // Luận đề trung tâm đứng im không được kéo
                  
                  draggedParticle = p;
                  p.isSnapped = false; // Gỡ ra khỏi slot khi bắt đầu kéo
                  offsetX = p.x - tX;
                  offsetY = p.y - tY;
                  p.vx = 0;
                  p.vy = 0;
                  
                  playClickSound(); // Âm thanh click khi nắm hạt
                  break;
                }}
              }}
            }}
            
            function moveDrag(tX, tY) {{
              if (draggedParticle) {{
                draggedParticle.x = tX + offsetX;
                draggedParticle.y = tY + offsetY;
                draggedParticle.vx = 0;
                draggedParticle.vy = 0;
              }}
            }}
            
            function endDrag() {{
              if (draggedParticle) {{
                // Kiểm định xem hạt thả ra có rơi vào gần vị trí đích (Target slot) không
                if (draggedParticle.tx !== null) {{
                  let d = dist(draggedParticle.x, draggedParticle.y, draggedParticle.tx, draggedParticle.ty);
                  // Tăng khoảng cách snap lên 60 * scaleFactor để dễ dàng bắt dính hơn
                  if (d < 60 * scaleFactor) {{
                    draggedParticle.x = draggedParticle.tx;
                    draggedParticle.y = draggedParticle.ty;
                    draggedParticle.isSnapped = true;
                    draggedParticle.vx = 0;
                    draggedParticle.vy = 0;
                    
                    playSnapSound(); // Âm thanh snap cạch cạch vui tai
                  }} else {{
                    draggedParticle.isSnapped = false;
                  }}
                }}
                draggedParticle = null;
              }}
            }}
            
            // Chuột (PC)
            function mousePressed() {{
              if (checkButtonClick(mouseX, mouseY)) return;
              startDrag(mouseX, mouseY);
            }}
            
            function mouseDragged() {{
              moveDrag(mouseX, mouseY);
            }}
            
            function mouseReleased() {{
              endDrag();
            }}
            
            // Cảm ứng (Smartphone)
            function touchStarted() {{
              let tX = mouseX;
              let tY = mouseY;
              if (touches.length > 0) {{
                tX = touches[0].x;
                tY = touches[0].y;
              }}
              if (checkButtonClick(tX, tY)) return;
              startDrag(tX, tY);
            }}
            
            function touchMoved() {{
              let tX = mouseX;
              let tY = mouseY;
              if (touches.length > 0) {{
                tX = touches[0].x;
                tY = touches[0].y;
              }}
              moveDrag(tX, tY);
              
              // CHẶN cuộn màn hình di động khi kéo thả
              if (draggedParticle) {{
                return false; 
              }}
            }}
            
            function touchEnded() {{
              endDrag();
            }}
            
            // Responsive khi xoay ngang/dọc điện thoại hoặc resize
            function windowResized() {{
              resizeCanvas(windowWidth, 550);
              calculateLayout();
              
              for (let i = 0; i < particles.length; i++) {{
                let p = particles[i];
                p.radius = (p.origSize / 2) * scaleFactor;
              }}
              
              assignTargets();
              
              // Đưa các hạt đã snap về vị trí co giãn mới
              for (let i = 0; i < particles.length; i++) {{
                let p = particles[i];
                if (p.isSnapped || p.isStatic) {{
                  p.x = p.tx;
                  p.y = p.ty;
                }}
              }}
            }}
          </script>
        </body>
        </html>
        """
        
        st.components.v1.html(p5_canvas_html, height=570, scrolling=False)

# ==========================================
# FOOTER
# ==========================================
st.markdown('<div class="footer">© 2026 Bản quyền thuộc về Đỗ Viết Cường - Trường PTDTNT Cao Lộc</div>', unsafe_allow_html=True)
