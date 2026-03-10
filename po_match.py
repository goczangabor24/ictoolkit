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

    # ÚJ: Extra infó keresése a PO után (szóköz + kisbetűk)
    extra_info = ""
    if po_match:
        after_po = path_text[po_match.end():]
        # Keresünk egy szóközt, majd kisbetűket (esetleg szóközzel elválasztva)
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
            if fc_pos < 0: continue
            window_start = max(0, fc_pos - 80)
            window_end = min(len(path_text), fc_pos + 80)
            window_text = path_text[window_start:window_end]

            month_num_match = re.search(r"\b(0[1-9]|1[0-2])\b", window_text)
            if month_num_match:
                month = month_num_match.group(1)
                break

            month_name_match = re.search(
                r"\b(january|jan|february|feb|march|mar|april|apr|may|june|jun|july|jul|august|aug|september|sept|sep|october|oct|november|nov|december|dec)\b",
                window_text, flags=re.IGNORECASE,
            )
            if month_name_match:
                month = month_names[month_name_match.group(1).lower()]
                break

    return fc, po, month, extra_info


def build_result_dataframe(insider_text: str, vim_text: str, paths_text: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    insider_pos = normalize_po_list(insider_text)
    vim_pos = normalize_po_list(vim_text)

    path_lines = [line.strip().strip('"') for line in paths_text.splitlines() if line.strip()]
    
    # fc_po_map: FC -> PO -> {'month': str, 'extra': str}
    fc_po_map = {}

    for path_line in path_lines:
        fc, po, month, extra = extract_fc_po_month(path_line)
        if not fc or not po:
            continue
        if fc not in fc_po_map:
            fc_po_map[fc] = {}
        # Elmentjük mindkét információt
        fc_po_map[fc][po] = {"month": month, "extra": extra}

    sorted_fcs = sorted(fc_po_map.keys())

    def create_rows(po_list):
        rows = []
        for po in po_list:
            row = {"PO Number": po}
            for fc in sorted_fcs:
                if po in fc_po_map[fc]:
                    data = fc_po_map[fc][po]
                    m = data["month"]
                    e = data["extra"]
                    # Összeállítjuk a szöveget: "DN available in 03 (georgian)"
                    status = f"DN available in {m}" if m else "DN available"
                    if e:
                        status += f" ({e})"
                    row[fc] = status
                else:
                    row[fc] = ""
            rows.append(row)
        return rows

    insider_rows = create_rows(insider_pos)
    vim_rows = create_rows(vim_pos)

    columns = ["PO Number"] + sorted_fcs
    insider_df = pd.DataFrame(insider_rows, columns=columns)
    vim_df = pd.DataFrame(vim_rows, columns=columns)

    if sorted_fcs:
        insider_df = insider_df[insider_df[sorted_fcs].replace("", pd.NA).notna().any(axis=1)]
        vim_df = vim_df[vim_df[sorted_fcs].replace("", pd.NA).notna().any(axis=1)]

    return insider_df, vim_df

# --- Az interaktív renderelés és a Streamlit UI rész változatlan marad ---
# (Csak a render_interactive_dn_table függvényt és a UI hívásokat kell megtartani)
