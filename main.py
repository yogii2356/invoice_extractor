import os
import re
import json
import time
import gradio as gr
import google.generativeai as genai
from utils.preprocessor import extract_text_by_page  # Still modular for OCR
from utils.ocr_engine import extract_text_from_image
from typing import Optional

from pydantic import BaseModel, Field


# ================================
# LLM + JSON Extraction Utilities
# ================================

json_response = ""  # shared across chatbot

# folder_path = "D:/ocr project/llm-project/data2"

def configure_gemini(api_key):
    genai.configure(api_key=api_key)
    return genai.GenerativeModel('gemini-2.5-flash')


def ask_llm_about_invoice(model, text, page_num):
 
    prompt = f"""

You are a financial document assistant.
Below is the raw  multiple invoices text:

{text}
Your job is to:
1. Extract and return ONLY the following fields in clean JSON format for all invoices:
   - invoice_number
   - company_name (Seller)
   - seller_address
   - seller_gstin
   - buyer_name
   - buyer_address
   - buyer_gstin
   - items (a list with item S.N., descriptions of Goods,HSN/SAC code, quantity, unit, list price, Discount, price and amount)
   - subtotal_before_gst
   - cgst
   - sgst
   - total_gst (sum of cgst and sgst or igst)
   - total_amount_after_gst
   - bank_details

Ensure the response is strictly a valid JSON object without any explanation or markdown formatting. Example format:
"if you find any null value in the invoice no need to mention those fields in the json data"

{{
    "invoice_number": "...",
    "company_name": "...",
    "seller_address": "...",
    "seller_gstin": "...",
    "buyer_name": "...",
    "buyer_address": "...",
    "buyer_gstin": "...",
    "items": [
        {{
            "S.N.": ...,
            "description of goods": "...",
            "HSN/SAG code": ...,
            "quantity": ...,
            "unit": "..."
            "list price": ...,
            "Discount": ...,
            "price": ...,
            "amount": ...,
        }}
    ],
    "subtotal_before_gst": ...,
    "cgst": ...,
    "sgst": ...,
    "total_gst": ...,
    "total_amount_after_gst": ...,
    "bank_details": ...
}}
"""
    
    for attempt in range(2):  # Retry up to 3 times
        try:
            response = model.generate_content(prompt)
            print(f"followimg is the responce of llm :\n{response.text}")
            global json_responce
            json_responce = response.text
            return response.text
        except Exception as e:
            print(f"LLM error: {e}")
            print("Rate limit hit or other error. Waiting 60 seconds...")
            time.sleep(60)
    return "LLM response could not be retrieved after multiple attempts."

# =======================
# Merge Helper Function
# =======================

def merge_invoice_pages(responses_by_page):
    """
    Given a dict mapping page_num -> parsed_json (dict or list),
    produce one merged invoice dict.
    """
    base = responses_by_page.get(1)
    if not isinstance(base, dict):
        raise ValueError("Page 1 must return a dict")

    merged_items = base.get("items", []).copy()

    # 
    # 
    # These are the financial fields we want to extract if missing in Page 1
    financial_keys = [
        "subtotal_before_gst",
        "cgst",
        "sgst",
        "total_gst",
        "total_amount_after_gst"
    ]

    for page_num, data in responses_by_page.items():
        if page_num == 1:
            continue

        #  Merge item lists
        if isinstance(data, list):
            merged_items.extend(data)
        elif isinstance(data, dict):
            if "items" in data and isinstance(data["items"], list):
                merged_items.extend(data["items"])
            
            #  Add missing financial fields if present
            for key in financial_keys:
                if key in data and data[key] is not None:
                    if key not in base or base[key] is None:
                        print(f" Found {key} in page {page_num}, adding to page 1")
                        base[key] = data[key]
        else:
            print(f" Page {page_num} didn’t return items")

    base["items"] = merged_items
    return base

# ======================
# Gradio Q&A Chat Bot
# ======================

def chat_with_invoice(message, history=None):
    system_prompt = (
        "You are an expert Chartered Accountant with deep knowledge of Indian tax laws. "
        "You will receive invoice data from different firms, companies, and organizations. "
        "Your job is to analyze the provided JSON data and answer user questions accurately, "
        "as per Indian financial and tax rules.\n"
        "Assume you have access to the internet and can use it as a reference to provide correct and complete answers.\n"
        "Treat the following words as equivalent when processing data:\n"
        "- 'date', 'dated', 'dates', 'Date', 'Dated' → all refer to 'date'.\n"
    )

    prompt = f"""{system_prompt}
You are provided with JSON invoice data delimited by triple backticks.
```{json_response}```

Answer the following question:
```{message}```

Your answer should be in plain readable text, not in JSON.
"""
    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f" Error generating answer: {e}"


# ============================
# Main Execution & UI Launch
# ============================

def main(folder_path, api_key):
    print("Starting Invoice Processing...")
    model = configure_gemini(api_key)

    responses = {}
    for file_name, page_num, text in extract_text_by_page(folder_path):
        print(f"\n🔹 Processing {file_name} - Page {page_num}")
        llm_raw = ask_llm_about_invoice(model, text, page_num)

        # Print raw response to inspect issues
        print("🔍 Raw LLM response:\n", llm_raw)

        match = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", llm_raw, re.DOTALL)
        if not match:
            print(f" No JSON block found in Page {page_num}")
            continue

        try:
            cleaned_json = match.group(1)
            print(" Matched JSON block:\n", cleaned_json)

            parsed = json.loads(cleaned_json)
            responses[page_num] = parsed
        except json.JSONDecodeError as e:
            print(f" JSON decode error on Page {page_num}: {e}")
            print(" Problematic JSON block:\n", cleaned_json)
            continue

    # Merge all pages into one structured invoice
    try:
        merged_invoice = merge_invoice_pages(responses)
    except Exception as e:
        print(" Error during merge_invoice_pages:", e)
        return

    #  Set combined JSON for Gradio
    try:
        global json_response
        json_response = json.dumps(merged_invoice, indent=2)
    except Exception as e:
        print(" Error serializing merged_invoice to JSON:", e)
        print(" Merged content:", merged_invoice)
        return

    #  Save to output file
    try:
        os.makedirs("output", exist_ok=True)
        with open("output/combined_output.json", "w", encoding="utf-8") as f:
            json.dump(merged_invoice, f, indent=4)
        print(" Combined JSON saved: output/combined_output.json")
    except Exception as e:
        print(" Error writing to file:", e)

    # # Launch Gradio UI
    # print(" Launching Gradio Invoice Q&A Bot...")
    # gr.ChatInterface(
    #     fn=chat_with_invoice,
    #     title=" Invoice Q&A Chatbot",
    #     type="messages",
    #     examples=[
    #         "What is the total invoice amount?",
    #         "List all items with quantities",
    #         "Who is the buyer and their GSTIN?"
    #     ]
    # ).launch()


if __name__ == '__main__':
    folder_path = "data3"
    Gemini_api_key = 'AIzaSyA3NZe9HouCuX_FxPcSHk33TcTtx9QUJW8' #change this to your api key 
    main(folder_path, Gemini_api_key)
