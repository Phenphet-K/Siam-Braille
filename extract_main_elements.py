import pefile
import re

pe = pefile.PE('TBTW2.exe')

def get_rcdata(res_name):
    for rsrc in pe.DIRECTORY_ENTRY_RESOURCE.entries:
        if rsrc.id == 10:
            for entry in rsrc.directory.entries:
                if str(entry.name) == res_name:
                    data_rva = entry.directory.entries[0].data.struct.OffsetToData
                    size = entry.directory.entries[0].data.struct.Size
                    return pe.get_data(data_rva, size)
    return None

data = get_rcdata('TSDIAPPFORM')

# Find all Delphi component declarations: e.g. TMainMenu, TMenuItem, TToolBar, TToolButton, TRichEdit, TStatusBar, etc.
# In Delphi DFM, components are named: <component_class> <component_name>
comp_pattern = rb'(T[A-Z][a-zA-Z0-9]+)\s+([A-Za-z0-9_]+)'

# Also extract all property assignments: Caption, Hint, Left, Top, Width, Height, ShortCut, OnClick
# Delphi strings in binary DFM can be scanned
strings_found = []
# Find all byte sequences that are TIS-620 or ASCII strings
raw_text = data

# Let's decode all readable tokens and their context
# Let's search specifically for MenuItems, ToolButtons, RichEdit, StatusBar
with open('main_window_elements.txt', 'w', encoding='utf-8') as out:
    out.write("=== MAIN WINDOW (TSDIAPPFORM) COMPONENTS & PROPERTIES ===\n\n")
    
    # Let's find all occurrences of Menu items, Captions, Actions, Hints
    lines = []
    # Tokenize by non-printable characters
    tokens = re.split(rb'[\x00-\x08\x0a-\x1f]+', data)
    
    current_object = "TSDIAppForm"
    out.write(f"Window: {current_object}\n")
    
    for t in tokens:
        if len(t) < 2:
            continue
        try:
            s_tis = t.decode('tis-620')
            s_asc = t.decode('latin1', errors='ignore')
            
            # Check if this is a component
            if re.match(r'^T[A-Z][a-zA-Z0-9_]+', s_asc):
                out.write(f"\n[Component] {s_asc}\n")
            elif any(k in s_asc for k in ['Caption', 'Hint', 'Name', 'OnClick', 'ShortCut', 'Action', 'Menu']):
                out.write(f"  {s_tis}\n")
            elif any(ord(c) >= 161 for c in s_tis): # Thai text
                out.write(f"    -> Text: {s_tis}\n")
            elif s_asc in ['MainMenu1', 'ToolBar1', 'StatusBar', 'RichEdit1', 'RichEdit2', 'FileOpen1', 'FileSave1', 'FileNew1', 'Translate1', 'Grade1', 'Grade2']:
                out.write(f"  ID: {s_asc}\n")
        except:
            pass

print("Saved main_window_elements.txt")
