import io
import zipfile
import base64
from pathlib import Path
import streamlit as st
from pypdf import PdfReader, PdfWriter
from email.message import EmailMessage
from email.utils import formatdate

# --- Helper function for filename sanitization ---
def sanitize_name(filename: str) -> str:
    stem = Path(filename).stem
    safe = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in stem).strip("_")
    return safe or "document"

# --- Page configuration ---
st.set_page_config(page_title="🐶 Hill's CMR Extractor", page_icon="📄", layout="centered")

st.title("🐶 Hill's CMR Extractor")
st.write(
    "Upload PDF files. This tool extracts the first pages and creates an **editable Outlook draft** "
    "with original files attached."
)

# --- File uploader ---
uploaded_files = st.file_uploader(
    "Upload PDF files",
    type=["pdf"],
    accept_multiple_files=True,
)

if uploaded_files:
    suffix_values: dict[str, str] = {}
    
    st.subheader("Output filename suffixes")
    header_cols = st.columns([3, 2])
    header_cols[0].markdown("**Original PDF name**")
    header_cols[1].markdown("**Suffix (Optional)**")

    for i, uploaded_file in enumerate(uploaded_files):
        clean_base = sanitize_name(uploaded_file.name)
        key = f"suffix_{clean_base}_{i}"
        
        cols = st.columns([3, 2])
        cols[0].text_input("Name", value=uploaded_file.name, disabled=True, key=f"name_{i}", label_visibility="collapsed")
        suffix_values[key] = cols[1].text_input(
            "Suffix", value="", key=key, placeholder="e.g. _v1", label_visibility="collapsed"
        )

    st.divider()

    # --- Validation Logic ---
    empty_suffixes = [key for key, val in suffix_values.items() if not val.strip()]
    
    col_btn1, col_btn2 = st.columns([1, 1])
    
    start_processing = False
    
    if empty_suffixes:
        st.warning(f"⚠️ **Note:** {len(empty_suffixes)} suffix field(s) are empty. These files will use their original names.")
        if st.button("🚀 Process Anyway", use_container_width=True, type="secondary"):
            start_processing = True
    else:
        if st.button("🚀 Process & Prepare ZIP", use_container_width=True, type="primary"):
            start_processing = True

    # --- Processing ---
    if start_processing:
        extracted_items = []      
        original_files_data = []  
        skipped_files = []

        with st.spinner("Processing documents..."):
            for i, uploaded_file in enumerate(uploaded_files):
                try:
                    file_bytes = uploaded_file.getvalue()
                    original_files_data.append((uploaded_file.name, file_bytes))
                    
                    reader = PdfReader(io.BytesIO(file_bytes))
                    if len(reader.pages) == 0:
                        skipped_files.append(f"{uploaded_file.name} (empty)")
                        continue

                    writer = PdfWriter()
                    writer.add_page(reader.pages[0])
                    
                    out_pdf_buffer = io.BytesIO()
                    writer.write(out_pdf_buffer)
                    
                    suffix_key = f"suffix_{sanitize_name(uploaded_file.name)}_{i}"
                    user_suffix = suffix_values.get(suffix_key, "").strip()
                    
                    stem = Path(uploaded_file.name).stem
                    final_stem = f"{stem}_{user_suffix}" if user_suffix else stem
                    final_name = f"{sanitize_name(final_stem)}.pdf"
                    
                    extracted_items.append((final_name, out_pdf_buffer.getvalue()))
                
                except Exception as e:
                    skipped_files.append(f"{uploaded_file.name} (Error: {e})")

        if extracted_items:
            # --- Generate Email Message (Base64 Fix) ---
            msg = EmailMessage()
            msg["Subject"] = "Hill's Delivery Notes"
            msg["To"] = ""  
            msg["Date"] = formatdate(localtime=True)
            msg["X-Unsent"] = "1" 
            
            body_text = "Hello,\n\nPlease find the Hill's delivery notes attached, please assign them to the invoices accordingly."
            msg.set_content(body_text)
            
            # Final fix for encoding
            for part in msg.walk():
                if part.get_content_maintype() == 'text':
                    part.replace_header('Content-Transfer-Encoding', 'base64')
                    encoded_body = base64.b64encode(body_text.encode('utf-8')).decode('ascii')
                    part.set_payload(encoded_body)

            # Attachments
            for orig_name, orig_data in original_files_data:
                msg.add_attachment(
                    orig_data,
                    maintype="application",
                    subtype="pdf",
                    filename=orig_name
                )
            
            email_bytes = msg.as_bytes()

            # --- Create final ZIP ---
            final_zip_buffer = io.BytesIO()
            with zipfile.ZipFile(final_zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("hills_delivery_email.eml", email_bytes)
                for name, data in extracted_items:
                    zf.writestr(f"extracted_pages/{name}", data)

            st.success("Processing complete!")
            
            st.download_button(
                label="📥 Download ZIP Package",
                data=final_zip_buffer.getvalue(),
                file_name="hills_package.zip",
                mime="application/zip",
                use_container_width=True
            )

        if skipped_files:
            st.warning("Skipped files:")
            for skip in skipped_files:
                st.write(f"- {skip}")
else:
    st.info("Please upload PDF files to start.")
