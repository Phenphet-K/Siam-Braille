import struct
import io

def decompile_dfm(raw_data):
    stream = io.BytesIO(raw_data)
    magic = stream.read(4)
    if magic != b'TPF0':
        return None
    
    out = []
    indent = 0
    
    def pad():
        return '  ' * indent

    def read_str():
        length = stream.read(1)[0]
        return stream.read(length)

    def read_value(val_type):
        if val_type == 1: # int8
            return str(struct.unpack('b', stream.read(1))[0])
        elif val_type == 2: # int16
            return str(struct.unpack('<h', stream.read(2))[0])
        elif val_type == 3: # int32
            return str(struct.unpack('<i', stream.read(4))[0])
        elif val_type == 4: # float
            return str(struct.unpack('<d', stream.read(8))[0])
        elif val_type == 5: # string
            return repr(read_str().decode('tis-620', errors='replace'))
        elif val_type == 6: # ident / symbol
            return read_str().decode('latin1', errors='replace')
        elif val_type == 7: # false
            return 'False'
        elif val_type == 8: # true
            return 'True'
        elif val_type == 9: # binary
            length = struct.unpack('<I', stream.read(4))[0]
            stream.read(length)
            return f'<{length} bytes binary>'
        elif val_type == 10: # set
            items = []
            while True:
                s = read_str().decode('latin1', errors='replace')
                if not s:
                    break
                items.append(s)
            return '[' + ', '.join(items) + ']'
        elif val_type == 11: # collection
            items = []
            while True:
                b = stream.read(1)
                if not b or b[0] == 0:
                    break
                # sub item
                item_str = read_value(b[0])
                items.append(str(item_str))
            return '(' + ', '.join(items) + ')'
        elif val_type == 12: # LString (Delphi 3+)
            length = struct.unpack('<I', stream.read(4))[0]
            s = stream.read(length)
            return repr(s.decode('tis-620', errors='replace'))
        elif val_type == 13: # WString
            length = struct.unpack('<I', stream.read(4))[0]
            s = stream.read(length * 2)
            return repr(s.decode('utf-16le', errors='replace'))
        elif val_type == 14: # Int64
            return str(struct.unpack('<q', stream.read(8))[0])
        else:
            return f'<unknown type {val_type}>'

    def parse_object():
        nonlocal indent
        flags = stream.read(1)
        if not flags:
            return
        # Object header
        type_name = read_str().decode('latin1', errors='replace')
        obj_name = read_str().decode('latin1', errors='replace')
        
        out.append(f"{pad()}object {obj_name}: {type_name}")
        indent += 1
        
        # Properties
        while True:
            prop_len = stream.read(1)
            if not prop_len or prop_len[0] == 0:
                break # end of properties
            prop_name = (prop_len + stream.read(prop_len[0] - 1) if prop_len[0] > 1 else prop_len) # wait
            # actually Delphi property name: 1 byte len, then chars
            stream.seek(-1, io.SEEK_CUR)
            prop_name = read_str().decode('latin1', errors='replace')
            if not prop_name:
                break
                
            val_type_b = stream.read(1)
            if not val_type_b:
                break
            val_type = val_type_b[0]
            val = read_value(val_type)
            out.append(f"{pad()}{prop_name} = {val}")

        # Sub objects
        while True:
            b = stream.read(1)
            if not b:
                break
            if b[0] == 0: # end of object
                break
            stream.seek(-1, io.SEEK_CUR)
            parse_object()

        indent -= 1
        out.append(f"{pad()}end")

    try:
        parse_object()
    except Exception as e:
        out.append(f"// Error parsing remaining DFM: {e}")
        
    return "\n".join(out)

# Test on Form 16 (Offset 0xBEAE4)
with open('TBTW2.exe', 'rb') as f:
    f.seek(0xBEAE4)
    raw = f.read(40000)

result = decompile_dfm(raw)
with open('form16_decompiled.dfm', 'w', encoding='utf-8') as out:
    out.write(result)
print("Decompiled Form 16 successfully to form16_decompiled.dfm!")
