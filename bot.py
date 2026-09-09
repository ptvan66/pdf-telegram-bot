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
GEMINI_MODEL     = "gemini-3.6-flash"   # miễn phí, nhanh, đủ mạnh

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Khởi tạo Gemini client
gemini_client = genai.Client(api_key=GOOGLE_API_KEY)

# ── Prompt trích xuất dữ liệu ─────────────────────────────────────────────────
EXTRACTION_PROMPT = """Bạn là chuyên gia trích xuất dữ liệu từ hồ sơ kiểm nghiệm. Phân tích văn bản PDF dưới đây và trích xuất thông tin theo đúng quy tắc:

=== QUY TẮC TRÍCH XUẤT ===

## ĐỐI VỚI HỒ SƠ BIÊN BẢN LẤY MẪU:
Trích xuất chính xác 100%:
1. Tên tổ chức, cá nhân
2. Địa chỉ
3. Tên sản phẩm, hàng hóa (xuống hàng với từng tên sản phẩm)
4. Dạng sản phẩm (CHỈ lấy nếu văn bản có chữ "dạng ..."; không lấy mùi, màu; không ghi "dạng mẫu")
5. Mã mẫu (phân tách bằng dấu phẩy, không ghi chữ "mã mẫu")
6. Số tờ khai HQ (nếu không có trong biên bản thì tìm ở Trang Phụ lục; phải đúng định dạng 12 chữ số)

Ghép thành 1 câu cho từng sản phẩm theo mẫu:
[Tên sản phẩm]: [dạng - chữ d viết thường, BỎ TRỐNG nếu không có], bảo quản ở nhiệt độ thường, [mã mẫu], tờ khai số [12 số - BỎ TRỐNG nếu không có]

## ĐỐI VỚI HỒ SƠ PHIẾU YÊU CẦU THỬ NGHIỆM:
Trích xuất chính xác 100%:
7. Tên và địa chỉ trong mục "Thông tin khách hàng"
8. Tên mẫu (xuống hàng với từng tên mẫu, kèm số tờ khai hải quan nếu có)

=== ĐỊNH DẠNG ĐẦU RA ===

Nếu tìm thấy BIÊN BẢN LẤY MẪU:
--- BIÊN BẢN LẤY MẪU ---
Tổ chức/Cá nhân: [tên]
Địa chỉ: [địa chỉ]

Danh sách mẫu:
[câu ghép từng sản phẩm, mỗi sản phẩm 1 dòng]

Nếu tìm thấy PHIẾU YÊU CẦU THỬ NGHIỆM:
--- PHIẾU YÊU CẦU THỬ NGHIỆM ---
Khách hàng: [tên]
Địa chỉ: [địa chỉ]

Danh sách mẫu:
[tên mẫu + tờ khai nếu có, mỗi mẫu 1 dòng]

Nếu tài liệu có cả hai loại, xuất đủ cả hai phần theo thứ tự xuất hiện.
Nếu không tìm thấy, ghi: "Không tìm thấy [loại hồ sơ] trong tài liệu."

=== NỘI DUNG PDF ===
{pdf_text}
"""

# ── Hàm đọc PDF ───────────────────────────────────────────────────────────────
def extract_text_from_pdf(pdf_path: str) -> str:
    """Trích xuất toàn bộ text từ PDF, giữ nguyên layout."""
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
    """Gửi text đến Gemini để trích xuất dữ liệu."""
    prompt = EXTRACTION_PROMPT.format(pdf_text=pdf_text)
    response = gemini_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0,          # kết quả ổn định, không sáng tạo
            max_output_tokens=4096,
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
        "• Dung lượng tối đa 20MB\n"
        "• Hoàn toàn MIỄN PHÍ với Google AI Studio"
    )

async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Nhận PDF → đọc text → gọi Gemini → trả kết quả."""
    document = update.message.document

    if not document.file_name.lower().endswith(".pdf"):
        await update.message.reply_text("⚠️ Vui lòng gửi file PDF.")
        return

    processing_msg = await update.message.reply_text("⏳ Đang tải file PDF...")

    tmp_path = None
    try:
        # Tải file
        file = await context.bot.get_file(document.file_id)
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            await file.download_to_drive(tmp.name)
            tmp_path = tmp.name

        # Đọc PDF
        await processing_msg.edit_text("⏳ Đang đọc nội dung PDF...")
        pdf_text = extract_text_from_pdf(tmp_path)

        # Gọi Gemini
        await processing_msg.edit_text("🤖 Đang phân tích với Gemini AI...")
        result = process_with_gemini(pdf_text)

        # Xoá thông báo chờ
        await processing_msg.delete()

        # Gửi kết quả (Telegram giới hạn 4096 ký tự/tin nhắn)
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
        print("\nChạy lệnh sau rồi thử lại:")
        print('  export TELEGRAM_TOKEN="token_của_bạn"')
        print('  export GOOGLE_API_KEY="key_của_bạn"')
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
