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
# TAB 2: PHÒNG THÍ NGHIỆM VĂN HỌC
# ------------------------------------------
with tab2:
    st.title("🧪 Phòng Thí Nghiệm Văn Học")
    st.markdown("**Ứng dụng học tập thông minh: Trực quan hóa cấu trúc sơ đồ tư duy bằng hạt vật lý tương tác.**")
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
                with st.spinner("Gemini đang thiết kế cấu trúc hạt vật lý cho chủ đề... Vui lòng đợi trong giây lát."):
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
                            "Bạn là một chuyên gia giảng dạy Ngữ văn THPT độc đáo và sáng tạo. "
                            "Nhiệm vụ của bạn là phân tích chủ đề nghị luận xã hội được cung cấp và thiết kế cấu trúc mạng lưới hạt tư duy tương tác vật lý (dưới dạng JSON).\\n"
                            "Hãy tạo ra từ 6 đến 9 hạt tư duy phân chia đều cho các góc nhìn:\\n"
                            "- Khái niệm, khía cạnh cốt lõi (lực âm nhẹ hoặc dương nhẹ gần 0).\\n"
                            "- Các dẫn chứng thực tế tiêu biểu (BẮT BUỘC có lực dương lớn, từ 1.5 đến 4.0, đại diện cho thực tế trĩu nặng đặt ở dưới đáy).\\n"
                            "- Các bài học hành động, bài học nhận thức cụ thể (BẮT BUỘC có lực âm lớn, từ -4.0 đến -1.5, đại diện cho ý chí hướng lên trên).\\n\\n"
                            "YÊU CẦU ĐỊNH DẠNG: Trả về kết quả là một chuỗi mảng JSON hợp lệ duy nhất, tuyệt đối không có thêm bất kỳ lời dẫn giải thích hay định dạng markdown nào khác ngoài JSON.\\n"
                            "Mỗi đối tượng trong mảng phải chứa đầy đủ và chính xác các trường sau:\\n"
                            "- id: số nguyên duy nhất từ 1 trở đi\\n"
                            "- ten: tên ngắn gọn của hạt tư duy (2-5 từ, ví dụ: 'Nghị lực của Nick Vujicic', 'Rèn luyện thói quen tốt', 'Lòng vị tha')\\n"
                            "- luc: số thực trong khoảng từ -5.0 đến 5.0 (lực dương hạt sẽ trĩu xuống, lực âm hạt sẽ bay lên)\\n"
                            "- mau: mã màu HEX (dùng màu tươi sáng phù hợp với từng loại hạt, ví dụ màu ấm/đỏ/cam cho dẫn chứng, màu xanh lá/dương cho bài học, màu pastel cho khái niệm)\\n"
                            "- size: số nguyên từ 70 đến 100 (kích thước hạt theo pixel để ghi chữ rõ ràng)\\n"
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
                        
                        if isinstance(parsed_data, list):
                            st.session_state.literature_json = parsed_data
                            st.success("✅ Đã thiết lập thành công phòng thí nghiệm vật lý văn học!")
                        else:
                            st.error("❌ Dữ liệu trả về từ Gemini không đúng định dạng danh sách hạt. Vui lòng thử lại.")
                    except Exception as e:
                        st.error(f"❌ Lỗi xử lý từ Gemini: {str(e)}")
                        
    if st.session_state.literature_json:
        st.subheader("🔮 Phòng thí nghiệm hạt vật lý tương tác")
        st.markdown(
            "💡 **Hướng dẫn chạm vuốt di động & máy tính:**\\n"
            "- Sử dụng ngón tay chạm vuốt (trên điện thoại) hoặc nhấp chuột kéo thả (trên máy tính) để di chuyển các hạt tự do.\\n"
            "- Các hạt có **Lực Dương (Dẫn chứng/Thực tiễn)** sẽ tự động trĩu nặng xuống đáy màn hình.\\n"
            "- Các hạt có **Lực Âm (Bài học/Nhận thức)** sẽ tự động nhẹ nhàng bay lên phía trên màn hình."
        )
        
        # Chuyển đổi dữ liệu JSON sang chuỗi an toàn
        import json
        literature_data_str = json.dumps(st.session_state.literature_json, ensure_ascii=False)
        
        # Mã HTML nhúng p5.js tương thích cao với di động
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
              height: 500px;
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
            let draggedParticle = null;
            let offsetX = 0;
            let offsetY = 0;
            
            function setup() {{
              // Sử dụng width=100% bằng cách đo chiều rộng cửa sổ trình duyệt (windowWidth)
              let canvas = createCanvas(windowWidth, 500);
              canvas.parent('canvas-container');
              
              // Khởi tạo các hạt tư duy tư thế ngẫu nhiên ở khu vực trung tâm
              for (let i = 0; i < particleData.length; i++) {{
                let data = particleData[i];
                let pSize = parseInt(data.size) || 80;
                particles.push({{
                  id: data.id,
                  ten: data.ten,
                  luc: parseFloat(data.luc) || 0,
                  mau: data.mau || '#3B82F6',
                  radius: pSize / 2,
                  x: random(pSize, windowWidth - pSize),
                  y: random(150, 350),
                  vx: 0,
                  vy: 0
                }});
              }}
            }}
            
            function draw() {{
              background('#F1F5F9');
              
              // Vẽ đường phân cách nét đứt tinh tế
              stroke('#CBD5E1');
              strokeWeight(2);
              drawingContext.setLineDash([6, 12]);
              line(0, height / 2, width, height / 2);
              drawingContext.setLineDash([]); // Tắt nét đứt
              
              // Chú thích phân vùng hoạt động của các hạt
              noStroke();
              fill('#64748B');
              textSize(12);
              textStyle(BOLD);
              textAlign(LEFT, TOP);
              text("🎈 KHÁT VỌNG & BÀI HỌC HÀNH ĐỘNG (Bay lên)", 15, 15);
              
              textAlign(LEFT, BOTTOM);
              text("⚓ THỰC TIỄN & DẪN CHỨNG KHÁI QUÁT (Trĩu xuống)", 15, height - 15);
              
              // Cập nhật vật lý và giới hạn biên cho từng hạt
              for (let i = 0; i < particles.length; i++) {{
                let p = particles[i];
                
                if (p !== draggedParticle) {{
                  // Lực đẩy/hút dọc theo trục Y dựa trên thuộc tính lực (luc)
                  p.vy += p.luc * 0.12; 
                  
                  // Giảm tốc/Ma sát
                  p.vx *= 0.93;
                  p.vy *= 0.93;
                  
                  p.x += p.vx;
                  p.y += p.vy;
                }}
                
                // Giới hạn biên cứng, nảy lại khi va chạm viền
                if (p.x < p.radius) {{ p.x = p.radius; p.vx *= -0.5; }}
                if (p.x > width - p.radius) {{ p.x = width - p.radius; p.vx *= -0.5; }}
                if (p.y < p.radius) {{ p.y = p.radius; p.vy *= -0.5; }}
                if (p.y > height - p.radius) {{ p.y = height - p.radius; p.vy *= -0.5; }}
              }}
              
              // Tính toán va chạm đẩy nhau giữa các hạt để không bị xếp đè lên nhau
              for (let i = 0; i < particles.length; i++) {{
                for (let j = i + 1; j < particles.length; j++) {{
                  let p1 = particles[i];
                  let p2 = particles[j];
                  let d = dist(p1.x, p1.y, p2.x, p2.y);
                  let minDist = p1.radius + p2.radius + 6;
                  if (d < minDist) {{
                    let overlap = minDist - d;
                    let angle = atan2(p2.y - p1.y, p2.x - p1.x);
                    let forceX = cos(angle) * overlap * 0.25;
                    let forceY = sin(angle) * overlap * 0.25;
                    
                    if (p1 !== draggedParticle) {{
                      p1.vx -= forceX;
                      p1.vy -= forceY;
                    }}
                    if (p2 !== draggedParticle) {{
                      p2.vx += forceX;
                      p2.vy += forceY;
                    }}
                  }}
                }}
              }}
              
              // Vẽ các hạt tư duy và đổ bóng tương tác
              for (let i = 0; i < particles.length; i++) {{
                let p = particles[i];
                
                if (p === draggedParticle) {{
                  // Đổ bóng đậm hơn khi kéo thả hạt
                  fill('rgba(15, 23, 42, 0.15)');
                  noStroke();
                  ellipse(p.x + 3, p.y + 5, p.radius * 2 + 6);
                }}
                
                fill(p.mau);
                stroke('#FFFFFF');
                strokeWeight(3);
                ellipse(p.x, p.y, p.radius * 2);
                
                // Vẽ chữ hiển thị thông tin bên trong hạt tư duy
                drawWrappedText(p.ten, p.x, p.y, p.radius);
              }}
            }}
            
            // Hàm vẽ tự động phân chia dòng văn bản cho vừa khít hạt tròn
            function drawWrappedText(txt, x, y, radius) {{
              fill('#FFFFFF');
              noStroke();
              textAlign(CENTER, CENTER);
              textSize(11);
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
              
              let lineHeight = 13;
              let startY = y - (lines.length - 1) * lineHeight / 2;
              for (let i = 0; i < lines.length; i++) {{
                text(lines[i], x, startY + i * lineHeight);
              }}
            }}
            
            // Khởi tạo hoạt động kéo thả cho chuột và chạm cảm ứng
            function startDrag(tX, tY) {{
              for (let i = particles.length - 1; i >= 0; i--) {{
                let p = particles[i];
                let d = dist(tX, tY, p.x, p.y);
                if (d < p.radius) {{
                  draggedParticle = p;
                  offsetX = p.x - tX;
                  offsetY = p.y - tY;
                  p.vx = 0;
                  p.vy = 0;
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
              draggedParticle = null;
            }}
            
            // Sử dụng các sự kiện chuột tiêu chuẩn trên PC
            function mousePressed() {{
              startDrag(mouseX, mouseY);
            }}
            
            function mouseDragged() {{
              moveDrag(mouseX, mouseY);
            }}
            
            // Sử dụng các sự kiện chạm vuốt trên Điện thoại thông minh (Smartphones)
            function touchStarted() {{
              let tX = mouseX;
              let tY = mouseY;
              if (touches.length > 0) {{
                tX = touches[0].x;
                tY = touches[0].y;
              }}
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
              
              // CHẶN hành vi cuộn trang của trình duyệt di động khi đang kéo thả hạt
              if (draggedParticle) {{
                return false; 
              }}
            }}
            
            function touchEnded() {{
              endDrag();
            }}
            
            // Tự động co giãn khi kích thước màn hình thay đổi
            function windowResized() {{
              resizeCanvas(windowWidth, 500);
            }}
          </script>
        </body>
        </html>
        """
        
        st.components.v1.html(p5_canvas_html, height=520, scrolling=False)

# ==========================================
# FOOTER
# ==========================================
st.markdown('<div class="footer">© 2026 Bản quyền thuộc về Đỗ Viết Cường - Trường PTDTNT Cao Lộc</div>', unsafe_allow_html=True)
