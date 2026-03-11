import io
import zipfile
from pathlib import Path
import streamlit as st
from pypdf import PdfReader, PdfWriter
from email.message import EmailMessage
from email.utils import formatdate
from email import contentmanager

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
    header_cols[1].markdown("**Suffix (optional)**")

    for i, uploaded_file in enumerate(uploaded_files):
        clean_base = sanitize_name(uploaded_file.name)
        key = f"suffix_{clean_base}_{i}"
        
        cols = st.columns([3, 2])
        cols[0].text_input("Name", value=uploaded_file.name, disabled=True, key=f"name_{i}", label_visibility="collapsed")
        suffix_values[key] = cols[1].text_input(
            "Suffix", value="", key=key, placeholder="e.g. _extract", label_visibility="collapsed"
        )

    st.divider()

    if st.button("🚀 Process & Prepare All-in-One ZIP", use_container_width=True):
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
            # --- Generate Email Message ---
            msg = EmailMessage()
            msg["Subject"] = "Hill's Delivery Notes"
            msg["To"] = ""  
            msg["Date"] = formatdate(localtime=True)
            msg["X-Unsent"] = "1" 
            
            body_text = "Hello,\n\nPlease find the Hill's delivery notes attached, please assign them to the invoices accordingly."
            
            # We set the content and then force the encoding to 8bit to avoid "=" signs
            msg.set_content(body_text)
            
            # This logic avoids the "ValueError" by correctly managing headers
            main_part = msg.get_body() if msg.is_multipart() else msg
            main_part.replace_header('Content-Transfer-Encoding', '8bit')

            # Attachments (Originals)
            for orig_name, orig_data in original_files_data:
                msg.add_attachment(
                    orig_data,
                    maintype="application",
                    subtype="pdf",
                    filename=orig_name
                )
            
            # Use a policy that supports 8bit to prevent re-encoding during output
            email_bytes = msg.as_bytes(policy=msg.policy.clone(cte_type='8bit'))

            # --- Create final ZIP ---
            final_zip_buffer = io.BytesIO()
            with zipfile.ZipFile(final_zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("hills_delivery_email.eml", email_bytes)
                for name, data in extracted_items:
                    zf.writestr(f"extracted_pages/{name}", data)

            st.success("Processing complete!")
            
            st.download_button(
                label="📥 Download ZIP (PDFs + Fixed Email Draft)",
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

st.divider()
st.caption("Policy-based 8bit Encoding | Outlook Draft Mode | Character Fix Applied")
