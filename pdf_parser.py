import fitz  # PyMuPDF


def extract_text_from_pdf(pdf_path, max_pages=5):
    text_list = []

    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    pages_to_read = min(total_pages, max_pages)

    print(f"PDF總頁數：{total_pages}")

    for i in range(pages_to_read):
        page = doc.load_page(i)
        text = page.get_text("text")

        print(f"\n--- 第 {i+1} 頁（抓到 {len(text)} 字）---")
        text_list.append(text)

    doc.close()
    return "\n".join(text_list)


if __name__ == "__main__":
    pdf_path = "sample.pdf"

    try:
        result = extract_text_from_pdf(pdf_path, max_pages=3)
        print("\n====== 最終輸出（前500字）======")
        print(result[:500])
    except Exception as e:
        print("解析失敗：", e)