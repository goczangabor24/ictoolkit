import html
import json
import re

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components


# --- helper functions ---
def normalize_po_list(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def extract_fc_po_month(path_text: str) -> tuple[str, str, str, str]:
    fc_match = re.search(r"\b([A-Z]{3})\b", path_text)
    fc = fc_match.group(1) if fc_match else ""

    po_match = re.search(r"\b(1\d{6}|4\d{9})\b", path_text)
    po = po_match.group(1) if po_match else ""

    # Extra infó keresése a PO után (szóköz + kisbetűk)
    extra_info = ""
    if po_match:
        after_po = path_text[po_match.end():]
        # Keresünk egy szóközt, majd kisbetűket
        extra_match = re.search(r"^ ([a-z\s]+)", after_po)
        if extra_match:
            extra_info = extra_match.group(1).strip()

    month = ""
    month_names = {
        "january": "01", "jan": "01", "february": "02", "feb": "02",
        "march": "03", "mar": "03", "april": "04", "apr": "04", "may": "05",
        "june": "06", "jun": "06", "july": "07", "jul": "07", "august": "08",
        "aug": "08", "september": "09", "sep": "09", "sept": "09",
        "october": "10", "oct": "10", "november": "11", "nov": "11",
        "december": "12", "dec": "12",
    }

    if fc:
        fc_positions = [m.start() for m in re.finditer(rf"\b{re.escape(fc)}\b", path_text)]
        for fc_pos in fc_positions or [path_text.find(fc)]:
            if fc_pos < 0:
                continue
            window_start = max(0, fc_pos - 80)
            window_end = min(len(path_text), fc_pos + 80)
            window_text = path_text[window_start:window_end]

            month_num_match = re.search(r"\b(0[1-9]|1[0-2])\b", window_text)
            if month_num_match:
                month = month_num_match.group(1)
                break

            month_name_match = re.search(
                r"\b(january|jan|february|feb|march|mar|april|apr|may|june|jun|july|jul|august|aug|september|sept|sep|october|oct|november|nov|december|dec)\b",
                window_text,
                flags=re.IGNORECASE,
            )
            if month_name_match:
                month = month_names[month_name_match.group(1).lower()]
                break

    return fc, po, month, extra_info


def build_result_dataframe(insider_text: str, vim_text: str, paths_text: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    insider_pos = normalize_po_list(insider_text)
    vim_pos = normalize_po_list(vim_text)

    path_lines = [line.strip().strip('"') for line in paths_text.splitlines() if line.strip()]
    fc_po_map = {}

    for path_line in path_lines:
        fc, po, month, extra = extract_fc_po_month(path_line)
        if not fc or not po:
            continue
        if fc not in fc_po_map:
            fc_po_map[fc] = {}
        fc_po_map[fc][po] = {"month": month, "extra": extra}

    sorted_fcs = sorted(fc_po_map.keys())

    def process_rows(pos_list):
        rows = []
        for po in pos_list:
            row = {"PO Number": po}
            for fc in sorted_fcs:
                if po in fc_po_map[fc]:
                    data = fc_po_map[fc][po]
                    m = data["month"]
                    e = data["extra"]
                    val = f"DN available in {m}" if m else "DN available"
                    if e:
                        val += f" ({e})"
                    row[fc] = val
                else:
                    row[fc] = ""
            rows.append(row)
        return rows

    insider_rows = process_rows(insider_pos)
    vim_rows = process_rows(vim_pos)

    columns = ["PO Number"] + sorted_fcs
    insider_df = pd.DataFrame(insider_rows, columns=columns)
    vim_df = pd.DataFrame(vim_rows, columns=columns)

    if sorted_fcs:
        insider_df = insider_df[insider_df[sorted_fcs].replace("", pd.NA).notna().any(axis=1)]
        vim_df = vim_df[vim_df[sorted_fcs].replace("", pd.NA).notna().any(axis=1)]

    return insider_df, vim_df


def render_interactive_dn_table(df: pd.DataFrame) -> None:
    fc_columns = [col for col in df.columns if col != "PO Number"]
    match_totals = {
        col: int(df[col].fillna("").astype(str).str.startswith("DN available").sum())
        for col in fc_columns
    }

    payload_json = json.dumps({
        "columns": list(df.columns),
        "rows": df.fillna("").astype(str).to_dict(orient="records"),
        "match_totals": match_totals,
    })

    html_block = """
    <!doctype html>
    <html>
    <head>
      <meta charset="utf-8" />
      <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 0.5rem; background: white; }
        .hint { margin: 0 0 12px 0; font-size: 14px; color: #333; }
        .table-wrap { overflow-x: auto; border: 1px solid #d9d9d9; border-radius: 10px; }
        table { border-collapse: collapse; width: 100%; min-width: 900px; }
        th, td { border: 1px solid #e6e6e6; padding: 8px 10px; text-align: left; white-space: nowrap; font-size: 14px; }
        th { background: #f7f7f7; font-weight: 700; position: sticky; top: 0; z-index: 1; vertical-align: top; }
        .header-main { display: block; font-weight: 700; }
        .header-sub { display: block; margin-top: 2px; font-size: 12px; color: #666; font-weight: 400; }
        td.dn-cell { cursor: pointer; user-select: none; }
        td.dn-cell.selected { outline: 2px solid #1f77ff; outline-offset: -2px; background: #eaf2ff; }
        td.dn-cell.green { background: #c6efce !important; color: #006100; font-weight: 700; }
      </style>
    </head>
    <body>
      <div class="hint"><strong>How to use:</strong> Click a cell, then press <strong>Ctrl + Enter</strong> to toggle green.</div>
      <div class="table-wrap">
        <table id="dnTable"></table>
      </div>
      <script>
        const payload = __PAYLOAD_JSON__;
        const table = document.getElementById('dnTable');

        function escapeHtml(value) {
          return String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#039;');
        }

        function updateHeaderCounts() {
          payload.columns.forEach(col => {
            const header = document.querySelector(`th[data-col="${col}"] .header-sub`);
            if (!header) return;
            const total = Number(payload.match_totals[col] || 0);
            const completed = document.querySelectorAll(`td.dn-cell.green[data-fc="${col}"]`).length;
            header.textContent = `${completed}/${total} completed`;
          });
        }

        function buildTable() {
          const thead = document.createElement('thead');
          const headRow = document.createElement('tr');
          payload.columns.forEach(col => {
            const th = document.createElement('th');
            th.dataset.col = col;
            th.innerHTML = `<span class="header-main">${escapeHtml(col)}</span>`;
            if (col !== 'PO Number') {
              const total = payload.match_totals[col] || 0;
              th.innerHTML += `<span class="header-sub">0/${total} completed</span>`;
            }
            headRow.appendChild(th);
          });
          thead.appendChild(headRow);
          table.appendChild(thead);

          const tbody = document.createElement('tbody');
          payload.rows.forEach(row => {
            const tr = document.createElement('tr');
            payload.columns.forEach(col => {
              const td = document.createElement('td');
              const val = String(row[col] || '');
              td.innerHTML = escapeHtml(val);
              if (val.startsWith('DN available')) {
                td.classList.add('dn-cell');
                td.dataset.fc = col;
                td.onclick = () => {
                  document.querySelectorAll('.selected').forEach(el => el.classList.remove('selected'));
                  td.classList.add('selected');
                };
              }
              tr.appendChild(td);
            });
            tbody.appendChild(tr);
          });
          table.appendChild(tbody);
          updateHeaderCounts();
        }

        document.onkeydown = (e) => {
          if (e.ctrlKey && e.key === 'Enter') {
            const sel = document.querySelector('.selected');
            if (sel) { sel.classList.toggle('green'); updateHeaderCounts(); }
          }
        };
        buildTable();
      </script>
    </body>
    </html>
    """
    html_block = html_block.replace("__PAYLOAD_JSON__", payload_json)
    components.html(html_block, height=600, scrolling=True)


st.set_page_config(page_title="PO Collector", page_icon="📋", layout="wide")
st.title("PO Collector")

col1, col2 = st.columns(2)
with col1:
    st.markdown("## **INSIDER**")
    insider_input = st.text_area("Paste Insider PO numbers", height=220)
with col2:
    st.markdown("## **VIM**")
    vim_input = st.text_area("Paste VIM PO numbers", height=220)

st.markdown("## **FILE PATHS**")
paths_input = st.text_area("Paste file paths", height=220)

insider_df, vim_df = build_result_dataframe(insider_input, vim_input, paths_input)

st.markdown("## **INTERACTIVE RESULT**")
if insider_df.empty and vim_df.empty:
    st.info("Paste PO numbers and/or file paths to see the matched result automatically.")
else:
    if not insider_df.empty:
        st.markdown("### **INSIDER**")
        render_interactive_dn_table(insider_df)
    if not vim_df.empty:
        st.markdown("### **VIM**")
        render_interactive_dn_table(vim_df)

    csv_parts = []
    if not insider_df.empty:
        csv_parts.append("INSIDER\n" + insider_df.to_csv(index=False))
    if not vim_df.empty:
        csv_parts.append("VIM\n" + vim_df.to_csv(index=False))
    
    # JAVÍTOTT RÉSZ: a \n karakter most már helyesen, egy sorban van a stringgel
    csv_data = ("\n".join(csv_parts)).encode("utf-8")

    st.download_button(
        label="Download CSV",
        data=csv_data,
        file_name="po_dn_status_by_fc.csv",
        mime="text/csv",
    )
