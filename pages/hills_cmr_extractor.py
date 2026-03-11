import io
import zipfile
from pathlib import Path
import streamlit as st
from pypdf import PdfReader, PdfWriter
from email.message import EmailMessage

# --- Segédfüggvény a fájlnevek tisztításához ---
def sanitize_name(filename: str) -> str:
    stem = Path(filename).stem
    # Csak betűk, számok, kötőjel és alulvonás maradjon
    safe = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in stem).strip("_")
    return safe or "document"

# --- Oldal beállítása ---
st.set_page_config(page_title="🐶 Hill's CMR Extractor", page_icon="📄", layout="centered")

st.title("🐶 Hill's CMR Extractor")
st.write(
    "Töltsd fel a PDF-eket! Az app kivonatolja az első oldalakat egy ZIP-be, "
    "és generál egy Outlook e-mail tervezetet az eredeti fájlokkal."
)

# --- Fájl feltöltés ---
uploaded_files = st.file_uploader(
    "Válaszd ki a PDF fájlokat",
    type=["pdf"],
    accept_multiple_files=True,
)

if uploaded_files:
    suffix_values: dict[str, str] = {}
    
    st.subheader("Fájlnév utótagok (Suffix)")
    st.info("Itt adhatsz hozzá extra nevet a kivonatolt PDF-ekhez. Az e-mailben az eredeti nevek maradnak.")

    # Táblázatszerű elrendezés a suffixeknek
    header_cols = st.columns([3, 2])
    header_cols[0].markdown("**Eredeti fájlnév**")
    header_cols[1].markdown("**Utótag (opcionális)**")

    for i, uploaded_file in enumerate(uploaded_files):
        # Egyedi kulcs generálása a widgeteknek
        clean_base = sanitize_name(uploaded_file.name)
        key = f"suffix_{clean_base}_{i}"
        
        cols = st.columns([3, 2])
        cols[0].text_input("Név", value=uploaded_file.name, disabled=True, key=f"name_{i}", label_visibility="collapsed")
        suffix_values[key] = cols[1].text_input(
            "Suffix", 
            value="", 
            key=key, 
            placeholder="pl. _v1", 
            label_visibility="collapsed"
        )

    st.divider()

    # --- Feldolgozás indítása ---
    if st.button("🚀 Feldolgozás és letöltések előkészítése", use_container_width=True):
        extracted_items = []      # Kivonatolt első oldalak (módosított névvel)
        original_files_data = []  # Eredeti fájlok az e-mailhez
        skipped_files = []

        with st.spinner("Munka folyamatban..."):
            for i, uploaded_file in enumerate(uploaded_files):
                try:
                    # Fájl tartalmának beolvasása
                    file_bytes = uploaded_file.getvalue()
                    original_files_data.append((uploaded_file.name, file_bytes))
                    
                    # PDF feldolgozás (első oldal kivágása)
                    reader = PdfReader(io.BytesIO(file_bytes))
                    
                    if len(reader.pages) == 0:
                        skipped_files.append(f"{uploaded_file.name} (üres)")
                        continue

                    writer = PdfWriter()
                    writer.add_page(reader.pages[0])
                    
                    out_pdf_buffer = io.BytesIO()
                    writer.write(out_pdf_buffer)
                    
                    # Új fájlnév összeállítása a suffix-szel
                    suffix_key = f"suffix_{sanitize_name(uploaded_file.name)}_{i}"
                    user_suffix = suffix_values.get(suffix_key, "").strip()
                    
                    stem = Path(uploaded_file.name).stem
                    final_stem = f"{stem}_{user_suffix}" if user_suffix else stem
                    final_name = f"{sanitize_name(final_stem)}.pdf"
                    
                    extracted_items.append((final_name, out_pdf_buffer.getvalue()))
                
                except Exception as e:
                    skipped_files.append(f"{uploaded_file.name} (Hiba: {e})")

        # --- Eredmények megjelenítése ---
        if extracted_items:
            st.success(f"Sikeresen feldolgozva: {len(extracted_items)} fájl.")
            
            col1, col2 = st.columns(2)

            # 1. Kivonatolt ZIP letöltése
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
                for name, data in extracted_items:
                    zf.writestr(name, data)
            
            col1.download_button(
                label="📥 Kivonatolt PDF-ek (ZIP)",
                data=zip_buffer.getvalue(),
                file_name="hills_extracted_pages.zip",
                mime="application/zip",
                use_container_width=True
            )

            # 2. Outlook E-mail (.eml) generálása
            msg = EmailMessage()
            msg["Subject"] = "Hill's Delivery Notes"
            msg["To"] = "" # Itt megadhatsz egy fix e-mail címet is
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

            col2.download_button(
                label="📧 Outlook E-mail készítése",
                data=msg.as_bytes(),
                file_name="hills_delivery_email.eml",
                mime="message/rfc822",
                use_container_width=True,
                help="Letölt egy .eml fájlt, amit az Outlookban megnyitva azonnal küldhetsz."
            )

            # Lista a feldolgozott fájlokról
            with st.expander("Megnézem a generált fájlneveket"):
                for name, _ in extracted_items:
                    st.write(f"✅ {name}")

        if skipped_files:
            st.warning("Néhány fájlt nem sikerült feldolgozni:")
            for skip in skipped_files:
                st.write(f"- {skip}")

else:
    st.info("Kérlek, tölts fel legalább egy PDF fájlt a kezdéshez.")

st.divider()
st.caption("Használt könyvtárak: streamlit, pypdf | Formátum: RFC822 (Outlook kompatibilis)")
