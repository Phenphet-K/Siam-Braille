import os
import re

with open('TBTW2.exe', 'rb') as f:
    data = f.read()

dfm_indices = [m.start() for m in re.finditer(b'TPF0', data)]
print(f"Total Delphi DFM forms found: {len(dfm_indices)}")

# Let's write a simple Delphi DFM binary de-serializer
# Delphi TPF0 format:
# byte 0..3: 'TPF0'
# then stream of object definitions

def decode_delphi_string(b):
    try:
        return b.decode('tis-620')
    except Exception:
        return b.decode('latin1', errors='replace')

forms_info = []

for i, idx in enumerate(dfm_indices):
    # Find approximate end of form (next TPF0 or resource boundary)
    next_idx = dfm_indices[i+1] if i + 1 < len(dfm_indices) else idx + 30000
    chunk = data[idx:min(next_idx, idx + 50000)]
    
    # Extract visible strings (ASCII / TIS-620)
    # Delphi strings: length prefixed or null terminated
    # Let's search for strings and property names
    words = re.findall(rb'[\x20-\x7e\xa1-\xfb]{2,}', chunk)
    words_decoded = []
    for w in words:
        try:
            words_decoded.append(w.decode('tis-620'))
        except Exception:
            words_decoded.append(w.decode('latin1', errors='ignore'))
            
    first_few = words_decoded[:15]
    print(f"\n--- Form {i+1} at offset 0x{idx:X} ---")
    print("Header/Components:", " | ".join(first_few))
    
    # Save extracted strings for this form
    forms_info.append({
        'offset': idx,
        'tokens': words_decoded
    })

with open('extracted_forms.txt', 'w', encoding='utf-8') as out:
    for i, f_info in enumerate(forms_info):
        out.write(f"\n=================== FORM {i+1} (Offset 0x{f_info['offset']:X}) ===================\n")
        out.write("\n".join(f_info['tokens']))
        out.write("\n")

print("\nSaved all extracted form UI elements to extracted_forms.txt")
