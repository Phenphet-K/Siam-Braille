import pefile
import struct
import io
import json

pe = pefile.PE('TBTW2.exe')

def get_rcdata_entries():
    res = {}
    for rsrc in pe.DIRECTORY_ENTRY_RESOURCE.entries:
        if rsrc.id == 10:
            for entry in rsrc.directory.entries:
                name = str(entry.name) if entry.name else f"ID_{entry.id}"
                data_rva = entry.directory.entries[0].data.struct.OffsetToData
                size = entry.directory.entries[0].data.struct.Size
                res[name] = pe.get_data(data_rva, size)
    return res

def decode_tis620(raw):
    try:
        return raw.decode('tis-620')
    except:
        return raw.decode('latin1', errors='replace')

def parse_dfm_stream(stream, indent=0):
    lines = []
    def pad():
        return '  ' * indent

    def read_str():
        b = stream.read(1)
        if not b:
            return None
        length = b[0]
        if length == 0:
            return ""
        raw = stream.read(length)
        return decode_tis620(raw)

    def read_ident():
        b = stream.read(1)
        if not b:
            return None
        length = b[0]
        if length == 0:
            return ""
        return stream.read(length).decode('latin1', errors='replace')

    def parse_value(v_type):
        if v_type == 1:
            val = struct.unpack('b', stream.read(1))[0]
            return str(val)
        elif v_type == 2:
            val = struct.unpack('<h', stream.read(2))[0]
            return str(val)
        elif v_type == 3:
            val = struct.unpack('<i', stream.read(4))[0]
            return str(val)
        elif v_type == 4: # Float
            # 10 bytes extended
            stream.read(10)
            return "0.0"
        elif v_type == 5: # ShortString
            s = read_str()
            return repr(s)
        elif v_type == 6: # Ident
            return read_ident()
        elif v_type == 7: # False
            return "False"
        elif v_type == 8: # True
            return "True"
        elif v_type == 9: # Binary
            length = struct.unpack('<I', stream.read(4))[0]
            stream.read(length)
            return f"<{length} bytes binary>"
        elif v_type == 10: # Set
            items = []
            while True:
                s = read_ident()
                if not s:
                    break
                items.append(s)
            return "[" + ", ".join(items) + "]"
        elif v_type == 11: # Collection
            items = []
            while True:
                b = stream.read(1)
                if not b or b[0] == 0:
                    break
                # item in collection:
                stream.seek(-1, io.SEEK_CUR)
                # read item
                sub_lines = []
                while True:
                    p_len = stream.read(1)
                    if not p_len or p_len[0] == 0:
                        break
                    p_name = decode_tis620(stream.read(p_len[0]))
                    vt = stream.read(1)[0]
                    vv = parse_value(vt)
                    sub_lines.append(f"{p_name} = {vv}")
                items.append("item " + "; ".join(sub_lines) + " end")
            return "(\n" + "\n".join("  " * (indent + 1) + it for it in items) + "\n" + pad() + ")"
        elif v_type == 12: # LString
            length = struct.unpack('<I', stream.read(4))[0]
            raw = stream.read(length)
            return repr(decode_tis620(raw))
        elif v_type == 13: # WString
            length = struct.unpack('<I', stream.read(4))[0]
            raw = stream.read(length * 2)
            return repr(raw.decode('utf-16le', errors='replace'))
        elif v_type == 14: # Int64
            val = struct.unpack('<q', stream.read(8))[0]
            return str(val)
        else:
            return f"<type_{v_type}>"

    # Read object header
    type_name = read_ident()
    if not type_name:
        return lines
    obj_name = read_ident()
    lines.append(f"{pad()}object {obj_name}: {type_name}")
    indent += 1

    # Read properties until 0 byte
    while True:
        b = stream.read(1)
        if not b or b[0] == 0:
            break
        prop_len = b[0]
        prop_name = decode_tis620(stream.read(prop_len))
        v_type_b = stream.read(1)
        if not v_type_b:
            break
        v_type = v_type_b[0]
        v_val = parse_value(v_type)
        lines.append(f"{pad()}{prop_name} = {v_val}")

    # Read child objects until 0 byte
    while True:
        pos = stream.tell()
        b = stream.read(1)
        if not b or b[0] == 0:
            break
        stream.seek(pos)
        child_lines = parse_dfm_stream(stream, indent)
        lines.extend(child_lines)

    indent -= 1
    lines.append(f"{pad()}end")
    return lines

entries = get_rcdata_entries()
for name, data in entries.items():
    if data.startswith(b'TPF0'):
        stream = io.BytesIO(data[4:])
        dfm_lines = parse_dfm_stream(stream)
        filename = f"dfm_{name}.txt"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("\n".join(dfm_lines))
        print(f"Exported {name} -> {filename} ({len(dfm_lines)} lines)")
