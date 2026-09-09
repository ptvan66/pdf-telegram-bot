"""
Telegram Bot - Xử lý PDF Biên Bản Lấy Mẫu & Phiếu Yêu Cầu Thử Nghiệm
Sử dụng: Google AI Studio (Gemini) - Miễn phí
Yêu cầu: pip install python-telegram-bot pdfplumber google-genai
"""

import os
import logging
import tempfile
import pdfplumber
from google import genai
from google.genai import types
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ── Cấu hình ──────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN",    "YOUR_TELEGRAM_BOT_TOKEN")
GOOGLE_API_KEY   = os.environ.get("GOOGLE_API_KEY",    "YOUR_GOOGLE_API_KEY")
GEMINI_MODEL     = "gemini-3.6-flash"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

gemini_client = genai.Client(api_key=GOOGLE_API_KEY)

# ── Prompt trích xuất dữ liệu ─────────────────────────────────────────────────
EXTRACTION_PROMPT = """Bạn là chuyên gia trích xuất dữ liệu từ hồ sơ kiểm nghiệm. Đọc toàn bộ PDF và trích xuất TỪNG hồ sơ theo đúng thứ tự xuất hiện trong tài liệu.

=== QUY TẮC TRÍCH XUẤT ===

PHIẾU YÊU CẦU THỬ NGHIỆM - trích xuất:
- Số phiếu (VD: 3431/26/DV)
- Tên và địa chỉ trong mục "Thông tin khách hàng"
- Danh sách tên mẫu: mỗi tên mẫu 1 dòng riêng. Kèm số tờ khai hải quan (12 số) nếu có.

BIÊN BẢN LẤY MẪU - trích xuất:
- Số biên bản (VD: 1981/QĐ-TTKN)
- Tên tổ chức/cá nhân và địa chỉ
- Với TỪNG sản phẩm ghép thành câu:
  [Tên SP]: [dạng xxx nếu văn bản có chữ "dạng"; d viết thường; KHÔNG ghi "dạng mẫu"/mùi/màu; BỎ TRỐNG nếu không có], bảo quản ở nhiệt độ thường, [mã mẫu phân cách bằng dấu phẩy], tờ khai số [12 chữ số, tìm ở Phụ lục nếu không có trong biên bản; BỎ TRỐNG nếu không có]

=== ĐỊNH DẠNG ĐẦU RA BẮT BUỘC ===

Xuất TỪNG hồ sơ theo thứ tự xuất hiện. Template cố định:

Với PHIẾU YÊU CẦU THỬ NGHIỆM:
ĐỐI VỚI HỒ SƠ PHIẾU YÊU CẦU THỬ NGHIỆM (Số: [số phiếu])

1. Tên và địa chỉ: [tên công ty]. [địa chỉ]
2. Tên mẫu: [tên mẫu 1]
[tên mẫu 2]
[tên mẫu 3, tờ khai nếu có]

Với BIÊN BẢN LẤY MẪU:
ĐỐI VỚI HỒ SƠ BIÊN BẢN LẤY MẪU (Số: [số biên bản])

1. Tên tổ chức, cá nhân: [tên]
2. Địa chỉ: [địa chỉ]
3. Tên sản phẩm, hàng hóa: [Tên SP 1] [Tên SP 2] ...
4. [Tên SP 1]: [dạng nếu có], bảo quản ở nhiệt độ thường, [mã mẫu], tờ khai số [12 số]
[Tên SP 2]: [dạng nếu có], bảo quản ở nhiệt độ thường, [mã mẫu], tờ khai số [12 số]

Cách nhau 1 dòng trống giữa các hồ sơ.
KHÔNG thêm ghi chú hay giải thích ngoài template trên.

=== NỘI DUNG PDF ===
"""

# ── Hàm đọc PDF ───────────────────────────────────────────────────────────────
def extract_text_from_pdf(pdf_path: str) -> str:
    parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text(layout=True)
            if text and text.strip():
                parts.append(f"[TRANG {i+1}]\n{text}")
    if not parts:
        raise RuntimeError(
            "Không đọc được text từ PDF.\n"
            "PDF của bạn có thể là dạng scan/ảnh — cần OCR trước."
        )
    return "\n\n".join(parts)

# ── Gọi Gemini API ─────────────────────────────────────────────────────────────
def process_with_gemini(pdf_text: str) -> str:
    prompt = EXTRACTION_PROMPT + pdf_text
    response = gemini_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0,
            max_output_tokens=8192,
        )
    )
    return response.text

# ── Telegram Handlers ──────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 Xin chào! Tôi là bot xử lý hồ sơ kiểm nghiệm.\n\n"
        "📄 Gửi file PDF để tôi tự động trích xuất:\n"
        "• Thông tin từ Biên Bản Lấy Mẫu\n"
        "• Thông tin từ Phiếu Yêu Cầu Thử Nghiệm\n\n"
        "Gõ /help để xem hướng dẫn."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "📋 Hướng dẫn sử dụng:\n\n"
        "1. Gửi file PDF lên chat này\n"
        "2. Bot tự động xử lý và trích xuất dữ liệu\n"
        "3. Kết quả trả về trong vài giây\n\n"
        "⚠️ Lưu ý:\n"
        "• Chỉ hỗ trợ PDF dạng text (không phải scan)\n"
        "• Dung lượng tối đa 20MB"
    )

async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    document = update.message.document

    if not document.file_name.lower().endswith(".pdf"):
        await update.message.reply_text("⚠️ Vui lòng gửi file PDF.")
        return

    processing_msg = await update.message.reply_text("⏳ Đang tải file PDF...")

    tmp_path = None
    try:
        file = await context.bot.get_file(document.file_id)
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            await file.download_to_drive(tmp.name)
            tmp_path = tmp.name

        await processing_msg.edit_text("⏳ Đang đọc nội dung PDF...")
        pdf_text = extract_text_from_pdf(tmp_path)

        await processing_msg.edit_text("🤖 Đang phân tích với Gemini AI...")
        result = process_with_gemini(pdf_text)

        await processing_msg.delete()

        header = f"✅ Kết quả từ: {document.file_name}\n{'─'*40}\n\n"
        full_result = header + result

        if len(full_result) <= 4096:
            await update.message.reply_text(full_result)
        else:
            chunks = [full_result[i:i+4000] for i in range(0, len(full_result), 4000)]
            for idx, chunk in enumerate(chunks):
                prefix = f"(Phần {idx+1}/{len(chunks)})\n" if len(chunks) > 1 else ""
                await update.message.reply_text(prefix + chunk)

    except RuntimeError as e:
        await processing_msg.edit_text(f"❌ {str(e)}")
    except Exception as e:
        logger.error(f"Lỗi xử lý PDF: {e}", exc_info=True)
        await processing_msg.edit_text(f"❌ Lỗi không xác định:\n{str(e)}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    missing = []
    if TELEGRAM_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
        missing.append("TELEGRAM_TOKEN")
    if GOOGLE_API_KEY == "YOUR_GOOGLE_API_KEY":
        missing.append("GOOGLE_API_KEY")
    if missing:
        for var in missing:
            print(f"❌ Chưa cấu hình: {var}")
        return

    print(f"🚀 Bot khởi động | Model: {GEMINI_MODEL}")
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_pdf))
    print("✅ Bot đang chạy. Nhấn Ctrl+C để dừng.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
