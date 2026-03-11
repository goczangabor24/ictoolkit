import io
import zipfile
from pathlib import Path
import streamlit as st
from pypdf import PdfReader, PdfWriter
from email.message import EmailMessage

# --- Helper function for filename sanitization ---
def sanitize_name(filename: str) -> str:
    stem = Path(filename).stem
    safe = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in stem).strip("_")
    return safe or "document"

# --- Page configuration ---
st.set_page_config(page_title="🐶 Hill's CMR Extractor", page_icon="📄", layout="centered")

st.title("🐶 Hill's CMR Extractor")
st.write(
    "Upload PDF files. The app will extract the first pages into a ZIP file "
    "and include a ready-to-send Outlook email draft with the original files attached."
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
    st.info("Add an optional suffix for extracted pages. The email draft will use original filenames.")

    header_cols = st.columns([3, 2])
    header_cols[0].markdown("**Original PDF name**")
    header_cols[1].markdown("**Suffix (optional)**")

    for i, uploaded_file in enumerate(uploaded_files):
        clean_base = sanitize_name(uploaded_file.name)
        key = f"suffix_{clean_base}_{i}"
        
        cols = st.columns([3, 2])
        cols[0].text_input("Name", value=uploaded_file.name, disabled=True, key=f"name_{i}", label_visibility="collapsed")
        suffix_values[key] = cols[1].text_input(
            "Suffix", 
            value="", 
            key=key, 
            placeholder="e.g. _extract", 
            label_visibility="collapsed"
        )

    st.divider()

    # --- Processing ---
    if st.button("🚀 Process & Prepare All-in-One ZIP", use_container_width=True):
        extracted_items = []      # Processed first pages
        original_files_data = []  # Original files for the email
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
            msg.set_content(
                "Hello,\n\n"
                "Please find the Hill's delivery notes attached, "
                "please assign them to the invoices accordingly."
            )

            for orig_name, orig_data in original_files_data:
                msg.add_attachment(
                    orig_data,
                    maintype="application",
                    subtype="pdf",
                    filename=orig_name
                )
            
            email_bytes = msg.as_bytes()

            # --- Create final ZIP containing both PDFs and the Email Draft ---
            final_zip_buffer = io.BytesIO()
            with zipfile.ZipFile(final_zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
                # Add the email draft to the root of the ZIP
                zf.writestr("hills_delivery_email.eml", email_bytes)
                
                # Add the extracted PDFs
                for name, data in extracted_items:
                    zf.writestr(f"extracted_pages/{name}", data)

            st.success("Processing complete!")
            
            st.download_button(
                label="📥 Download ZIP (PDFs + Email Draft)",
                data=final_zip_buffer.getvalue(),
                file_name="hills_package.zip",
                mime="application/zip",
                use_container_width=True,
                help="This ZIP contains the extracted PDFs and the editable Outlook email draft."
            )

            with st.expander("Show processed files"):
                st.write("**Email Draft:** `hills_delivery_email.eml` (includes original files)")
                st.write("**Extracted Pages:**")
                for name, _ in extracted_items:
                    st.write(f"- {name}")

        if skipped_files:
            st.warning("The following files could not be processed:")
            for skip in skipped_files:
                st.write(f"- {skip}")

else:
    st.info("Please upload PDF files to start.")

st.divider()
st.caption("Requirements: streamlit, pypdf | Format: RFC822 (Outlook Compatible)")
