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
st.set_page_config(page_title="Công cụ số hóa", page_icon="📝", layout="wide")

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
# GIAO DIỆN CHÍNH (TABS)
# ==========================================
tab1, tab2 = st.tabs(["Xử lý văn bản", "Phòng thí nghiệm văn học"])

# ------------------------------------------
# TAB 1: XỬ LÝ VĂN BẢN (Quản lý nội trú trước đây, không dùng sidebar nữa)
# ------------------------------------------
with tab1:
    col_left, col_right = st.columns([1, 2])
    
    with col_left:
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
        
    with col_right:
        st.title("🏛️ Công cụ số hóa")
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
        else:
            st.info("👈 Vui lòng tải tài liệu lên từ bảng bên trái để bắt đầu bóc tách phân công công việc.")

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
        
    start_btn = st.button("Vào phòng thí nghiệm")
    
    if start_btn:
        if not topic_input.strip():
            st.warning("⚠️ Vui lòng nhập chủ đề nghị luận xã hội tư tưởng đạo lý!")
        else:
            if not configure_genai():
                st.error("⚠️ LỖI: Chưa cấu hình GOOGLE_API_KEY ở backend. Vui lòng kiểm tra mã nguồn (app.py) hoặc cấu hình Streamlit Secrets.")
            else:
                with st.spinner('Thầy Đỗ Viết Cường đang chuẩn bị "hóa chất" để các em vào phòng thí nghiệm...'):
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
        st.subheader("🔮 Sơ đồ hạt vật lý tương tác liên kết")
        st.markdown(
            "🎮 **LUẬT CHƠI & HƯỚNG DẪN:**\\n"
            "1. **Phía bên trái** là các ô tròn nét đứt (slots). Không còn nhãn chữ gợi ý mờ để thử thách sự hiểu bài của bạn!\\n"
            "2. **Phía bên phải** là các hạt luận điểm, dẫn chứng và **hạt tung hỏa mù (decoy)** nằm lộn xộn.\\n"
            "3. Sử dụng ngón tay chạm vuốt (Smartphone) hoặc chuột kéo thả (PC) đưa các hạt từ bên phải lắp vào ô trống bên trái. **Hạt có thể dính vào bất kỳ ô nào, tuy nhiên chỉ khi xếp đúng ô, đường liên kết phát sáng mới hiện ra**.\\n"
            "4. Các hạt hỏa mù (nội dung lệch lạc/sai) không có ô trống nào đúng để kết nối, hãy để chúng bay tự do bên phải.\\n"
            "5. Sau khi ghép xong, hãy nhấn nút **THỰC HIỆN THÍ NGHIỆM** ở góc dưới bên phải để kiểm tra. Nếu xếp sai/thiếu, **các hạt xếp sai sẽ nổ tung và văng về bên phải**! Nếu xếp đúng, **luồng sáng tư duy và pháo hoa rực rỡ sẽ xuất hiện chúc mừng**!"
        )
        
        # Chuyển đổi dữ liệu JSON sang chuỗi an toàn
        import json
        literature_data_str = json.dumps(st.session_state.literature_json, ensure_ascii=False)
        
        # Mã HTML nhúng p5.js với trò chơi ghép nối và hiệu ứng nổ tung/pháo hoa hạt vật lý
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
            let slots = []; // Chứa tọa độ các ô đích bên trái
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
            
            // Pháo hoa chào mừng chiến thắng
            let fireworks = [];
            
            // Trạng thái Popup thông báo lỗi & giải thích
            let showErrorPopup = false;
            let errorList = [];
            
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
              scaleFactor = windowWidth < 600 ? 0.68 : 1.0;
              
              if (windowWidth > 800) {{
                col1 = windowWidth * 0.07;
                col2 = windowWidth * 0.22;
                col3 = windowWidth * 0.38;
                startX = windowWidth * 0.52;
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
                  currentSlotId: null,
                  parentSlotId: null,
                  correctParentId: null,
                  isCorrectlySnapped: false,
                  tx: null,
                  ty: null
                }});
              }}
              
              // 2. Định nghĩa vị trí đích (Targets) và Slots
              assignTargets();
              
              // 3. Phân bổ vị trí khởi tạo: Luận đề nằm tĩnh bên trái, còn lại lộn xộn bên phải
              let rootNode = particles.find(p => p.nhomType === 'luan_de');
              for (let p of particles) {{
                if (rootNode && p.id === rootNode.id) {{
                  p.x = p.tx;
                  p.y = p.ty;
                }} else {{
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
              slots = []; // Clear trước khi gán
              
              let rootNode = particles.find(p => p.nhomType === 'luan_de') || particles[0];
              if (!rootNode) return;
              
              rootNode.tx = col1;
              rootNode.ty = 275;
              rootNode.isSnapped = true;
              rootNode.isStatic = true;
              rootNode.nhomType = 'luan_de';
              
              let outlineIds = [];
              for (let i = 0; i < links.length; i++) {{
                let link = links[i];
                let s = Number(link.source);
                let t = Number(link.target);
                if (s === rootNode.id) outlineIds.push(t);
                else if (t === rootNode.id) outlineIds.push(s);
              }}
              
              let outlineNodes = particles.filter(p => outlineIds.includes(p.id));
              outlineNodes.sort((a, b) => a.id - b.id);
              
              let oGroups = ['mo_bai', 'giai_thich', 'phan_tich_chung_minh', 'ban_luan_mo_rong', 'bai_hoc', 'ket_bai'];
              for (let i = 0; i < outlineNodes.length; i++) {{
                outlineNodes[i].nhomType = oGroups[i] || 'luan_diem';
              }}
              
              // Đặt vị trí cho các luận điểm ở cột 2
              let outlineYSpacing = [50, 140, 230, 320, 410, 500];
              for (let i = 0; i < outlineNodes.length; i++) {{
                let node = outlineNodes[i];
                node.tx = col2;
                node.ty = outlineYSpacing[i] || 275;
                
                // Đăng ký slot đích (chỉ có luận điểm cấp 1 được hiện slot nét đứt)
                slots.push({{ id: 'outline_' + node.id, x: col2, y: node.ty, pId: node.id }});
              }}
              
              // Tìm các hạt con chi tiết liên kết tương ứng với từng luận điểm
              childNodesMap = {{}};
              for (let outline of outlineNodes) {{
                let children = [];
                for (let i = 0; i < links.length; i++) {{
                  let link = links[i];
                  let sId = Number(link.source);
                  let tId = Number(link.target);
                  let oId = Number(outline.id);
                  
                  if (sId === oId && tId !== rootNode.id) {{
                    let targetNode = particles.find(p => p.id === tId);
                    if (targetNode) {{
                      targetNode.nhomType = 'chi_tiet';
                      children.push(targetNode);
                    }}
                  }} else if (tId === oId && sId !== rootNode.id) {{
                    let sourceNode = particles.find(p => p.id === sId);
                    if (sourceNode) {{
                      sourceNode.nhomType = 'chi_tiet';
                      children.push(sourceNode);
                    }}
                  }}
                }}
                childNodesMap[outline.id] = children;
              }}
              
              // Thiết lập correctParentId cho các hạt chi tiết con
              for (let i = 0; i < outlineNodes.length; i++) {{
                let outline = outlineNodes[i];
                let children = childNodesMap[outline.id] || [];
                for (let child of children) {{
                  child.correctParentId = outline.id;
                  child.tx = null;
                  child.ty = null;
                }}
              }}
              
              // Đánh dấu hạt hỏa mù (các hạt không phải luận đề, không phải luận điểm cấp 1 và không có parent)
              for (let i = 0; i < particles.length; i++) {{
                let p = particles[i];
                if (p.nhomType !== 'luan_de' && !outlineGroups.includes(p.nhomType) && !p.correctParentId) {{
                  p.nhomType = 'hoa_mu';
                  p.tx = null;
                  p.ty = null;
                }}
              }}
            }}
            
            function getChildren(parentId) {{
              let list = [];
              for (let link of links) {{
                if (Number(link.source) === parentId) {{
                  let p = particles.find(p => p.id === Number(link.target) && p.nhomType === 'chi_tiet');
                  if (p) list.push(p);
                }} else if (Number(link.target) === parentId) {{
                  let p = particles.find(p => p.id === Number(link.source) && p.nhomType === 'chi_tiet');
                  if (p) list.push(p);
                }}
              }}
              return list;
            }}
            
            function setupFireworks() {{
              fireworks = [];
              let palette = [
                {{ r: 255, g: 0, b: 127 }},
                {{ r: 255, g: 215, b: 0 }},
                {{ r: 0, g: 255, b: 204 }},
                {{ r: 255, g: 87, b: 51 }},
                {{ r: 57, g: 255, b: 20 }}
              ];
              for (let i = 0; i < 5; i++) {{
                let c = random(palette);
                fireworks.push({{
                  x: random(width * 0.2, width * 0.8),
                  y: height,
                  targetY: random(80, 220),
                  speed: random(5, 8),
                  exploded: false,
                  r: c.r,
                  g: c.g,
                  b: c.b,
                  particles: []
                }});
              }}
            }}
            
            function drawFireworks() {{
              for (let i = fireworks.length - 1; i >= 0; i--) {{
                let f = fireworks[i];
                if (!f.exploded) {{
                  f.y -= f.speed;
                  fill(f.r, f.g, f.b);
                  noStroke();
                  ellipse(f.x, f.y, 6);
                  
                  if (f.y <= f.targetY) {{
                    f.exploded = true;
                    // Sinh tàn pháo hoa
                    for (let j = 0; j < 35; j++) {{
                      let angle = random(TWO_PI);
                      let speed = random(1.5, 4.5);
                      f.particles.push({{
                        x: f.x,
                        y: f.y,
                        vx: cos(angle) * speed,
                        vy: sin(angle) * speed,
                        alpha: 255,
                        decay: random(3, 7)
                      }});
                    }}
                  }}
                }} else {{
                  let alive = false;
                  for (let j = 0; j < f.particles.length; j++) {{
                    let p = f.particles[j];
                    if (p.alpha > 0) {{
                      p.x += p.vx;
                      p.y += p.vy;
                      p.vy += 0.08; // trọng lực tàn pháo
                      p.alpha -= p.decay;
                      
                      fill(f.r, f.g, f.b, p.alpha);
                      noStroke();
                      ellipse(p.x, p.y, 4);
                      alive = true;
                    }}
                  }}
                  if (!alive) {{
                    fireworks.splice(i, 1);
                  }}
                }}
              }}
              
              // Tự động bắn tiếp pháo hoa mờ khi thắng cuộc
              if (showSuccessText && random(1) < 0.04) {{
                let palette = [
                  {{ r: 255, g: 0, b: 127 }},
                  {{ r: 255, g: 215, b: 0 }},
                  {{ r: 0, g: 255, b: 204 }},
                  {{ r: 255, g: 87, b: 51 }},
                  {{ r: 57, g: 255, b: 20 }}
                ];
                let c = random(palette);
                fireworks.push({{
                  x: random(width * 0.1, width * 0.9),
                  y: height,
                  targetY: random(80, 250),
                  speed: random(5, 8),
                  exploded: false,
                  r: c.r,
                  g: c.g,
                  b: c.b,
                  particles: []
                }});
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
              for (let i = 0; i < slots.length; i++) {{
                let slot = slots[i];
                stroke('#94A3B8');
                strokeWeight(1.5);
                drawingContext.setLineDash([4, 6]); // Nét đứt mờ
                noFill();
                ellipse(slot.x, slot.y, 88 * scaleFactor);
                drawingContext.setLineDash([]); // Tắt nét đứt
              }}
              
              // 2. Vẽ đường nối (Links)
              stroke('#94A3B8');
              strokeWeight(1.8);
              
              // Vẽ các đường nối cố định từ hạt luận đề (Root) đến 6 slot luận điểm lớn cấp 1 ở cột 2
              let rootNode = particles.find(p => p.nhomType === 'luan_de');
              if (rootNode) {{
                for (let slot of slots) {{
                  line(rootNode.x, rootNode.y, slot.x, slot.y);
                }}
              }}
              
              // Vẽ đường nối từ các slot luận điểm cấp 1 sang các hạt luận điểm cấp 2 đã snap vào slot đó (ĐÚNG hay SAI đều vẽ)
              for (let p of particles) {{
                if (p.isSnapped && p.parentSlotId) {{
                  let slot = slots.find(s => s.id === p.parentSlotId);
                  if (slot) {{
                    line(slot.x, slot.y, p.x, p.y);
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
                    if (child.isSnapped && child.parentSlotId === 'outline_' + currentP.id) {{
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
              
              // Cập nhật vị trí của các hạt cấp 2 / hạt hỏa mù đã snap vào các slot cấp 1 ở cột 2
              for (let i = 0; i < slots.length; i++) {{
                let slot = slots[i];
                let snappedChildren = particles.filter(p => p.isSnapped && p.parentSlotId === slot.id);
                // Sắp xếp theo ID để duy trì thứ tự ổn định
                snappedChildren.sort((a, b) => a.id - b.id);
                
                let count = snappedChildren.length;
                for (let k = 0; k < count; k++) {{
                  let child = snappedChildren[k];
                  child.x = col3;
                  if (count === 1) {{
                    child.y = slot.y;
                  }} else if (count === 2) {{
                    child.y = slot.y + (k === 0 ? -28 : 28) * scaleFactor;
                  }} else if (count === 3) {{
                    child.y = slot.y + (k === 0 ? -42 : (k === 1 ? 0 : 42)) * scaleFactor;
                  }} else {{
                    let spacing = 90 * scaleFactor / (count - 1);
                    child.y = slot.y - 45 * scaleFactor + k * spacing;
                  }}
                  child.vx = 0;
                  child.vy = 0;
                }}
              }}
              
              // 4. Cập nhật vật lý và va chạm cho các hạt
              for (let i = 0; i < particles.length; i++) {{
                let p = particles[i];
                
                if (p.isSnapped) {{
                  if (p.currentSlotId) {{
                    let slot = slots.find(s => s.id === p.currentSlotId);
                    if (slot) {{
                      p.x = slot.x;
                      p.y = slot.y;
                    }}
                  }}
                  // Hạt cấp 2 sử dụng parentSlotId và vị trí đã được tính toán ở trên
                  p.vx = 0;
                  p.vy = 0;
                }} else if (p.isStatic) {{
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
                fill(p.nhomType === 'hoa_mu' ? '#64748B' : p.mau);
                stroke('#FFFFFF');
                strokeWeight(3);
                ellipse(p.x, p.y, p.radius * 2);
                
                // Viết chữ trong hạt
                drawWrappedText(p.ten, p.x, p.y, p.radius);
              }}
              
              // 6. Vẽ pháo hoa chào mừng
              drawFireworks();
              
              // 7. Vẽ nút bấm THỰC HIỆN THÍ NGHIỆM (Tăng độ rộng lên 180 để chứa nhãn mới)
              let btnW = 180 * scaleFactor;
              let btnH = 38 * scaleFactor;
              let btnX = width - btnW - 15;
              let btnY = height - btnH - 15;
              
              let isHover = (mouseX > btnX && mouseX < btnX + btnW && mouseY > btnY && mouseY < btnY + btnH);
              fill(isHover ? '#0F766E' : '#0D9488');
              noStroke();
              rect(btnX, btnY, btnW, btnH, 19 * scaleFactor);
              
              fill(255);
              textSize(10.5 * scaleFactor);
              textAlign(CENTER, CENTER);
              textStyle(BOLD);
              text("THỰC HIỆN THÍ NGHIỆM", btnX + btnW/2, btnY + btnH/2);
              
              // 8. Vẽ Flash chớp màn hình khi lỗi
              if (flashFrames > 0) {{
                fill(239, 68, 68, map(flashFrames, 0, 15, 0, 100)); // Đỏ chớp tắt
                noStroke();
                rect(0, 0, width, height);
                flashFrames--;
              }}
              
              if (shakeFrames >= 0) {{
                pop(); // Kết thúc dịch chuyển rung lắc camera
              }}
              
              // 9. Hiển thị thông báo trạng thái
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
              
              // 10. Vẽ Bảng thông báo lỗi (Popup Card) và giải thích
              if (showErrorPopup) {{
                // Phủ màn xám mờ
                fill('rgba(15, 23, 42, 0.65)');
                noStroke();
                rect(0, 0, width, height);
                
                // Thẻ thông tin Card ở giữa màn hình
                let cardW = min(width * 0.9, 650);
                let cardH = min(height * 0.9, 470);
                let cardX = (width - cardW) / 2;
                let cardY = (height - cardH) / 2;
                
                fill('#FFFFFF');
                stroke('#EF4444');
                strokeWeight(4);
                rect(cardX, cardY, cardW, cardH, 12);
                
                // Tiêu đề Card
                fill('#DC2626');
                noStroke();
                textSize(17 * scaleFactor);
                textStyle(BOLD);
                textAlign(CENTER, TOP);
                text("💥 KẾT QUẢ THÍ NGHIỆM CHƯA CHÍNH XÁC! 💥", width / 2, cardY + 20);
                
                // Lời giải thích chung
                fill('#475569');
                textSize(12 * scaleFactor);
                textStyle(NORMAL);
                text("Hãy đọc kỹ gợi ý phía dưới để điều chỉnh vị trí các hạt:", width / 2, cardY + 45);
                
                // Vẽ danh sách lỗi
                textAlign(LEFT, TOP);
                textSize(11 * scaleFactor);
                let startY = cardY + 75;
                let maxVisible = Math.floor((cardH - 140) / 24); // số dòng lỗi hiển thị được
                
                for (let i = 0; i < errorList.length; i++) {{
                  if (i >= maxVisible) {{
                    fill('#94A3B8');
                    text(`... và còn ${{errorList.length - maxVisible}} lỗi khác chưa khắc phục.`, cardX + 30, startY + i * 24);
                    break;
                  }}
                  
                  let errText = errorList[i];
                  // Vẽ dấu chấm đầu dòng màu đỏ
                  fill('#EF4444');
                  ellipse(cardX + 22, startY + i * 24 + 6, 6);
                  
                  // Vẽ nội dung lỗi
                  fill('#1E293B');
                  text(errText, cardX + 35, startY + i * 24);
                }}
                
                // Vẽ nút "Làm lại theo hướng dẫn"
                let popBtnW = 230 * scaleFactor;
                let popBtnH = 38 * scaleFactor;
                let popBtnX = (width - popBtnW) / 2;
                let popBtnY = cardY + cardH - popBtnH - 20;
                
                let isPopHover = (mouseX > popBtnX && mouseX < popBtnX + popBtnW && mouseY > popBtnY && mouseY < popBtnY + popBtnH);
                fill(isPopHover ? '#B91C1C' : '#DC2626');
                noStroke();
                rect(popBtnX, popBtnY, popBtnW, popBtnH, 19 * scaleFactor);
                
                fill(255);
                textAlign(CENTER, CENTER);
                textSize(11.5 * scaleFactor);
                textStyle(BOLD);
                text("LÀM LẠI THEO HƯỚNG DẪN", popBtnX + popBtnW/2, popBtnY + popBtnH/2);
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
            
            // Hàm tổng hợp lỗi sai và giải thích chi tiết
            function evaluateMistakes() {{
              let list = [];
              
              // 1. Kiểm tra luận điểm cấp 1
              for (let slot of slots) {{
                let p = particles.find(other => other.isSnapped && other.currentSlotId === slot.id);
                let correctL1 = particles.find(other => other.id === slot.pId);
                let label = correctL1 ? correctL1.ten : "Không rõ";
                
                if (!p) {{
                  list.push(`Thiếu luận điểm cấp 1: Bạn chưa xếp hạt nào vào vị trí của "${{label}}".`);
                }} else if (p.id !== slot.pId) {{
                  list.push(`Sai luận điểm cấp 1: Hạt "${{p.ten}}" đang xếp ở vị trí của "${{label}}".`);
                }}
              }}
              
              // 2. Kiểm tra luận điểm cấp 2 (chi tiết) và hạt hỏa mù
              for (let p of particles) {{
                if (p.nhomType === 'chi_tiet') {{
                  if (!p.isSnapped || !p.parentSlotId) {{
                    list.push(`Thiếu liên kết: Ý "${{p.ten}}" chưa được kéo thả vào luận điểm nào.`);
                  }} else if (p.parentSlotId !== 'outline_' + p.correctParentId) {{
                    let currentParentSlot = slots.find(s => s.id === p.parentSlotId);
                    let currentParentP = particles.find(other => other.id === currentParentSlot.pId);
                    let correctParentP = particles.find(other => other.id === p.correctParentId);
                    
                    let currentLabel = currentParentP ? currentParentP.ten : "Không rõ";
                    let correctLabel = correctParentP ? correctParentP.ten : "Không rõ";
                    
                    list.push(`Sai liên kết: Ý "${{p.ten}}" đang xếp vào "${{currentLabel}}" (đúng ra phải thuộc "${{correctLabel}}").`);
                  }}
                }} else if (p.nhomType === 'hoa_mu') {{
                  if (p.isSnapped && p.parentSlotId) {{
                    let currentParentSlot = slots.find(s => s.id === p.parentSlotId);
                    let currentParentP = particles.find(other => other.id === currentParentSlot.pId);
                    let currentLabel = currentParentP ? currentParentP.ten : "Không rõ";
                    list.push(`Thông tin nhiễu: Ý "${{p.ten}}" là hạt hỏa mù (sai lệch), không được xếp vào "${{currentLabel}}".`);
                  }}
                }}
              }}
              
              return list;
            }}
            
            // Xử lý nổ tung và hoàn trả các hạt sai/hạt hỏa mù về bên phải khi bấm Làm lại
            function triggerResetOnError() {{
              showErrorPopup = false;
              
              // Kích hoạt rung lắc camera & chớp đỏ
              flashFrames = 15;
              shakeFrames = 25;
              
              playExplosionSound(); // Tiếng nổ tung!
              
              for (let i = 0; i < particles.length; i++) {{
                let p = particles[i];
                if (p.isStatic) continue;
                
                let shouldBlow = false;
                
                if (p.nhomType !== 'chi_tiet' && p.nhomType !== 'hoa_mu') {{
                  // Hạt luận điểm cấp 1
                  if (!p.isSnapped || p.currentSlotId !== 'outline_' + p.id) {{
                    shouldBlow = true;
                    p.isSnapped = false;
                    p.currentSlotId = null;
                    p.isCorrectlySnapped = false;
                  }}
                }} else if (p.nhomType === 'chi_tiet') {{
                  // Hạt chi tiết cấp 2
                  if (!p.isSnapped || p.parentSlotId !== 'outline_' + p.correctParentId) {{
                    shouldBlow = true;
                    p.isSnapped = false;
                    p.parentSlotId = null;
                    p.isCorrectlySnapped = false;
                  }}
                }} else if (p.nhomType === 'hoa_mu') {{
                  // Hạt hỏa mù
                  shouldBlow = true; // Luôn nổ văng nếu bị xếp hoặc chưa xếp đều bị đẩy nhẹ
                  p.isSnapped = false;
                  p.parentSlotId = null;
                  p.isCorrectlySnapped = false;
                }}
                
                if (shouldBlow) {{
                  let angle = random(-PI/4, PI/4);
                  let speed = random(14, 24);
                  p.vx = cos(angle) * speed;
                  p.vy = sin(angle) * speed;
                }}
              }}
            }}
            
            // Logic kiểm định hoàn thành bài học
            function checkCompletion() {{
              if (showErrorPopup) return; // Không cho phép check lặp lại khi popup đang hiển thị
              
              let mistakes = evaluateMistakes();
              
              if (mistakes.length === 0) {{
                showSuccessText = true;
                successTimer = 250;
                flowActive = true;
                flowStep = 0;
                flowProgress = 0.0;
                showExplosionText = false;
                
                setupFireworks(); // Bắn pháo hoa chào mừng!
                playSuccessSound(); // Nhạc chiến thắng!
              }} else {{
                // Thay vì nổ văng ngay lập tức, ta hiển thị popup chỉ lỗi
                showErrorPopup = true;
                errorList = mistakes;
                
                // Rung nhẹ camera và phát âm thanh cảnh báo lỗi
                shakeFrames = 10;
                playClickSound();
              }}
            }}
            
            function checkButtonClick(tX, tY) {{
              let btnW = 180 * scaleFactor;
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
                  if (p.nhomType !== 'chi_tiet' && p.nhomType !== 'hoa_mu') {{
                    p.currentSlotId = null;
                  }} else {{
                    p.parentSlotId = null;
                  }}
                  p.isCorrectlySnapped = false;
                  
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
                let isLevel1 = (draggedParticle.nhomType !== 'chi_tiet' && draggedParticle.nhomType !== 'hoa_mu');
                
                // Tìm kiếm ô slot trống gần nhất
                let closestSlot = null;
                let minDist = 99999;
                
                for (let i = 0; i < slots.length; i++) {{
                  let slot = slots[i];
                  
                  if (isLevel1) {{
                    // Đối với hạt cấp 1, slot phải chưa bị hạt cấp 1 khác chiếm đóng
                    let isOccupied = particles.some(other => 
                      other.isSnapped && 
                      other.currentSlotId === slot.id && 
                      other.id !== draggedParticle.id &&
                      other.nhomType !== 'chi_tiet' &&
                      other.nhomType !== 'hoa_mu'
                    );
                    if (!isOccupied) {{
                      let d = dist(draggedParticle.x, draggedParticle.y, slot.x, slot.y);
                      if (d < minDist) {{
                        minDist = d;
                        closestSlot = slot;
                      }}
                    }}
                  }} else {{
                    // Đối với luận điểm cấp 2, cho phép dính nhiều hạt vào cùng 1 ô luận điểm cấp 1
                    let d = dist(draggedParticle.x, draggedParticle.y, slot.x, slot.y);
                    if (d < minDist) {{
                      minDist = d;
                      closestSlot = slot;
                    }}
                  }}
                }}
                
                // Khoảng cách snap: cấp 1 là 60px, cấp 2 (thả trực tiếp lên hạt cấp 1) dùng 80px
                let snapThreshold = isLevel1 ? (60 * scaleFactor) : (80 * scaleFactor);
                
                if (closestSlot && minDist < snapThreshold) {{
                  if (isLevel1) {{
                    draggedParticle.x = closestSlot.x;
                    draggedParticle.y = closestSlot.y;
                    draggedParticle.isSnapped = true;
                    draggedParticle.currentSlotId = closestSlot.id;
                    draggedParticle.vx = 0;
                    draggedParticle.vy = 0;
                    draggedParticle.isCorrectlySnapped = (closestSlot.pId === draggedParticle.id);
                  }} else {{
                    // Hạt cấp 2 dính vào slot của hạt cấp 1
                    draggedParticle.isSnapped = true;
                    draggedParticle.parentSlotId = closestSlot.id;
                    draggedParticle.vx = 0;
                    draggedParticle.vy = 0;
                    draggedParticle.isCorrectlySnapped = (closestSlot.id === 'outline_' + draggedParticle.correctParentId);
                  }}
                  playSnapSound();
                }} else {{
                  draggedParticle.isSnapped = false;
                  if (isLevel1) {{
                    draggedParticle.currentSlotId = null;
                  }} else {{
                    draggedParticle.parentSlotId = null;
                  }}
                  draggedParticle.isCorrectlySnapped = false;
                }}
                draggedParticle = null;
              }}
            }}
            
            // Chuột (PC)
            function mousePressed() {{
              if (showErrorPopup) {{
                // Kiểm tra click vào nút "LÀM LẠI THEO HƯỚNG DẪN"
                let cardW = min(width * 0.9, 650);
                let cardH = min(height * 0.9, 470);
                let cardX = (width - cardW) / 2;
                let cardY = (height - cardH) / 2;
                
                let popBtnW = 230 * scaleFactor;
                let popBtnH = 38 * scaleFactor;
                let popBtnX = (width - popBtnW) / 2;
                let popBtnY = cardY + cardH - popBtnH - 20;
                
                if (mouseX > popBtnX && mouseX < popBtnX + popBtnW && mouseY > popBtnY && mouseY < popBtnY + popBtnH) {{
                  triggerResetOnError();
                }}
                return;
              }}
              
              if (checkButtonClick(mouseX, mouseY)) return;
              startDrag(mouseX, mouseY);
            }}
            
            function mouseDragged() {{
              if (showErrorPopup) return;
              moveDrag(mouseX, mouseY);
            }}
            
            function mouseReleased() {{
              if (showErrorPopup) return;
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
              
              if (showErrorPopup) {{
                let cardW = min(width * 0.9, 650);
                let cardH = min(height * 0.9, 470);
                let cardX = (width - cardW) / 2;
                let cardY = (height - cardH) / 2;
                
                let popBtnW = 230 * scaleFactor;
                let popBtnH = 38 * scaleFactor;
                let popBtnX = (width - popBtnW) / 2;
                let popBtnY = cardY + cardH - popBtnH - 20;
                
                if (tX > popBtnX && tX < popBtnX + popBtnW && tY > popBtnY && tY < popBtnY + popBtnH) {{
                  triggerResetOnError();
                }}
                return;
              }}
              
              if (checkButtonClick(tX, tY)) return;
              startDrag(tX, tY);
            }}
            
            function touchMoved() {{
              if (showErrorPopup) return;
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
              if (showErrorPopup) return;
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
              
              // Đưa các hạt đã snap về vị trí co giãn mới tương ứng với Slot của nó
              for (let i = 0; i < particles.length; i++) {{
                let p = particles[i];
                if (p.isSnapped) {{
                  if (p.currentSlotId) {{
                    let slot = slots.find(s => s.id === p.currentSlotId);
                    if (slot) {{
                      p.x = slot.x;
                      p.y = slot.y;
                    }}
                  }} else if (p.parentSlotId) {{
                    let slot = slots.find(s => s.id === p.parentSlotId);
                    if (slot) {{
                      p.x = col3;
                      p.y = slot.y;
                    }}
                  }}
                }} else if (p.isStatic) {{
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
