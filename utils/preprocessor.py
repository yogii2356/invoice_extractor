
# import fitz  # PyMuPDF

# def extract_text_from_pdf(pdf_path):
#     text = ""
#     with fitz.open(pdf_path) as doc:
#         for page in doc:
#             text += page.get_text()
#     return text


# import os
# import fitz  # PyMuPDF
# import io
# from PIL import Image
# import pytesseract

# def extract_text_from_folder(folder_path):
#     supported_exts = ['.pdf', '.png', '.jpeg', '.jpg', '.tiff']
#     combined_text = ""

#     for file_name in os.listdir(folder_path):
#         file_path = os.path.join(folder_path, file_name)
#         ext = os.path.splitext(file_path)[1].lower()

#         if ext in supported_exts:
#             text = f"\n=== Extracting from: {file_name} ===\n"
            
#             if ext == '.pdf':
#                 with fitz.open(file_path) as doc:
#                     for page_num, page in enumerate(doc):
#                         text += f"\n--- Page {page_num + 1} Text ---\n"
#                         text += page.get_text()

#                         for img_index, img in enumerate(page.get_images(full=True)):
#                             xref = img[0]
#                             base_image = doc.extract_image(xref)
#                             image_bytes = base_image["image"]
#                             image = Image.open(io.BytesIO(image_bytes))
#                             ocr_text = pytesseract.image_to_string(image)
#                             text += f"\n--- OCR from Image {img_index + 1} ---\n"
#                             text += ocr_text

#             elif ext in ['.png', '.jpeg', '.jpg', '.tiff']:
#                 image = Image.open(file_path)
#                 text += pytesseract.image_to_string(image)

#             combined_text += text + "\n\n"
#         else:
#             print(f"Skipping unsupported file: {file_name}")

#     return combined_text

import os
import fitz  # PyMuPDF
import io
from PIL import Image
import pytesseract

def extract_text_by_page(folder_path):
    supported_exts = ['.pdf', '.png', '.jpeg', '.jpg', '.tiff']

    for file_name in os.listdir(folder_path):
        file_path = os.path.join(folder_path, file_name)
        ext = os.path.splitext(file_path)[1].lower()

        if ext == '.pdf':
            with fitz.open(file_path) as doc:
                for page_num, page in enumerate(doc):
                    page_text = f"\n=== {file_name} | Page {page_num + 1} ===\n"
                    page_text += page.get_text()

                    for img_index, img in enumerate(page.get_images(full=True)):
                        xref = img[0]
                        base_image = doc.extract_image(xref)
                        image_bytes = base_image["image"]
                        image = Image.open(io.BytesIO(image_bytes))
                        ocr_text = pytesseract.image_to_string(image)
                        page_text += f"\n--- OCR from Image {img_index + 1} ---\n"
                        page_text += ocr_text

                    yield file_name, page_num + 1, page_text

        elif ext in supported_exts:
            image = Image.open(file_path)
            img_text = pytesseract.image_to_string(image)
            yield file_name, 1, img_text

        else:
            print(f"Skipping unsupported file: {file_name}")

