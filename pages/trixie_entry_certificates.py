import streamlit as st
import PyPDF2
import fitz  # PyMuPDF
import re
import pandas as pd
import streamlit.components.v1 as components
import io
from datetime import datetime

# 1. Setup
st.set_page_config(page_title="Zooplus - Trixie Entry Certificates", layout="wide")
st.title("🐶 Zooplus - Trixie Entry Certificates")


# Helper function for JS Copy Button
def copy_button(label, text_to_copy):
    button_uuid = re.sub(r"\W+", "", label)
    safe_text = text_to_copy.replace("\\", "\\\\").replace("`", "\\`")
    custom_js = f"""
        <button id="{button_uuid}" style="
            background-color: #4CAF50;
            color: white;
            border: none;
            padding: 5px 10px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;">
            📋 Copy All
        </button>
        <script>
        document.getElementById("{button_uuid}").addEventListener("click", function() {{
            const text = `{safe_text}`;
            navigator.clipboard.writeText(text).then(function() {{
                console.log('Copied!');
            }}, function(err) {{
                console.error('Could not copy text: ', err);
            }});
        }});
        </script>
    """
    components.html(custom_js, height=45)


# --- PATH DECODER ---
def extract_path_info(path):
    if not path or path == "No matching path found":
        return "Missing"

    p = str(path).replace("\\", "/")
    p = p.replace("_", "-")
    p = p.replace('"', "")

    m_map = {
        "jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05", "jun": "06",
        "jul": "07", "aug": "08", "sep": "09", "oct": "10", "nov": "11", "dec": "12"
    }

    loc_m = re.search(r"(WRO|BOR|KRO|BUD|ANR|BHX|BTS|MAD|MIL|ORY)", p, re.IGNORECASE)
    if not loc_m:
        return "Missing"

    loc = loc_m.group(1).upper()

    yr_m = re.search(r"(202[0-9]|2[0-9])", p)
    yr = yr_m.group(1) if yr_m else "2025"
    if len(yr) == 2:
        yr = "20" + yr

    mo = "01"
    for m_n, m_c in m_map.items():
        if m_n in p.lower():
            mo = m_c
            break
    else:
        num_m = re.search(loc + r"[^0-9]*([0-1][0-9])", p, re.IGNORECASE)
        if num_m:
            mo = num_m.group(1)

    return f"{loc} {mo}-{yr}"


def extract_po_numbers_from_pdf(pdf_bytes):
    reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
    text_content = ""

    for page in reader.pages:
        t = page.extract_text()
        if t:
            text_content += t

    pattern = r"\b(?:[1-2]\d{6}|4[07]\d{8})\b"
    raw_pos = re.findall(pattern, text_content)

    pos = []
    for item in raw_pos:
        if item not in pos:
            pos.append(item)

    return pos


def build_results(pos, clean_paths):
    results = []

    for po in pos:
        match = "No matching path found"
        for p_str in clean_paths:
            if po in p_str:
                match = p_str
                break

        info = extract_path_info(match)
        results.append({
            "PO Number": po,
            "Matched Path": match,
            "TO_COPY": info
        })

    return results


def style_results_table(df_display):
    def highlight_missing(row):
        if str(row["TO_COPY"]).strip().lower() == "missing":
            return ["background-color: #d32f2f; color: white;" for _ in row]
        return ["" for _ in row]

    return df_display.style.apply(highlight_missing, axis=1)


def add_labels_to_pdf(pdf_bytes, results):
    """
    1) Beírja az aktuális dátumot az Ausstellungsdatum alá (Wien, dátum).
    2) Az FC kódokat az Ort/Place/Lieu alá igazítja (fix 380-es X koordináta).
    3) A hónapot a jobb szélre igazítja.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    inserted_count = 0
    not_found = []

    font_size = 11
    y_offset = -3
    
    # Mai dátum előkészítése
    today_str = datetime.now().strftime("%d.%m.%Y")
    date_text = f"Wien, {today_str}"

    po_map = {
        str(row["PO Number"]): str(row["TO_COPY"])
        for row in results
        if str(row["TO_COPY"]).strip().lower() != "missing"
    }

    for page in doc:
        # --- 1. Aktuális dátum beírása az Ausstellungsdatum alá ---
        date_rects = page.search_for("Ausstellungsdatum")
        if date_rects:
            r_date = date_rects[0]
            # A felirat alá 18 egységgel (mint a beküldött kódodban)
            page.insert_text(
                (r_date.x0, r_date.y1 + 18),
                date_text,
                fontsize=11,
                fontname="helv",
                color=(0, 0, 0)
            )

        # --- 2. Táblázat sorainak kitöltése ---
        for po, label in po_map.items():
            rects = page.search_for(po)

            if rects:
                r = rects[0]
                y = r.y1 + y_offset

                # Szétválasztás: "KRO 09-2025" -> "KRO" és "09-2025"
                parts = label.split(" ")
                fc_code = parts[0] if len(parts) > 0 else ""
                date_val = parts[1] if len(parts) > 1 else ""

                # FC kód beírása (fix 380-es pozíció)
                page.insert_text(
                    (380, y),
                    fc_code,
                    fontsize=font_size,
                    fontname="helv",
                    color=(0, 0, 0)
                )

                # Dátum beírása (jobb szélre igazítva)
                if date_val:
                    date_width = fitz.get_text_length(date_val, fontname="helv", fontsize=font_size)
                    x_date = page.rect.x1 - 85 - date_width
                    
                    page.insert_text(
                        (x_date, y),
                        date_val,
                        fontsize=font_size,
                        fontname="helv",
                        color=(0, 0, 0)
                    )

                inserted_count += 1
                # Nem törünk ki a belső ciklusból, ha egy lapon többször is szerepelhet a PO

    output_bytes = doc.tobytes()
    doc.close()

    return output_bytes, inserted_count, not_found


# --- STEP 1: UPLOAD ---
st.subheader("1. Upload PDF")
pdf_file = st.file_uploader("Upload PDF to extract PO numbers", type=["pdf"])

if pdf_file is not None:
    try:
        pdf_bytes = pdf_file.read()
        pos = extract_po_numbers_from_pdf(pdf_bytes)

        if pos:
            st.success(f"Extracted {len(pos)} PO numbers.")
            
            oder_text = " ODER ".join(pos)
            or_text = " OR ".join(pos)

            c1, c2 = st.columns(2)
            with c1:
                st.text_area("German Windows:", value=oder_text, height=100)
                copy_button("German String", oder_text)
            with c2:
                st.text_area("English Windows:", value=or_text, height=100)
                copy_button("English String", or_text)

            st.divider()
            st.subheader("2. Paste paths")
            path_input = st.text_area("Paste paths here (one per line):", height=150)

            lines = path_input.split("\n")
            clean_p = [line.strip().replace('"', "") for line in lines if line.strip()]

            results = build_results(pos, clean_p)

            st.subheader("📋 Final Results")
            df_display = pd.DataFrame(results)[["PO Number", "TO_COPY"]]
            st.dataframe(style_results_table(df_display), use_container_width=True, hide_index=True)

            # --- STEP 3: GENERATE ---
            st.divider()
            st.subheader("3. Generate annotated PDF")

            if st.button("✍️ Create modified PDF"):
                modified_pdf_bytes, inserted_count, not_found = add_labels_to_pdf(pdf_bytes, results)
                st.success(f"Done. Annotated {inserted_count} positions.")

                original_name = pdf_file.name.rsplit(".", 1)[0]
                st.download_button(
                    "📥 Download Modified PDF",
                    data=modified_pdf_bytes,
                    file_name=f"{original_name}_annotated.pdf",
                    mime="application/pdf"
                )
        else:
            st.warning("No PO numbers found.")
    except Exception as e:
        st.error(f"Error: {e}")
