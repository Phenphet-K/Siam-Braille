import pefile
import struct
import io

pe = pefile.PE('TBTW2.exe')

def get_rcdata(res_name):
    for rsrc in pe.DIRECTORY_ENTRY_RESOURCE.entries:
        if rsrc.id == 10:
            for entry in rsrc.directory.entries:
                if str(entry.name) == res_name or entry.name == res_name:
                    data_rva = entry.directory.entries[0].data.struct.OffsetToData
                    size = entry.directory.entries[0].data.struct.Size
                    return pe.get_data(data_rva, size)
    return None

class DFMParser:
    def __init__(self, data):
        self.stream = io.BytesIO(data)
        self.out = []
        self.indent = 0

    def pad(self):
        return '  ' * self.indent

    def read_byte(self):
        b = self.stream.read(1)
        return b[0] if b else None

    def read_str(self):
        b = self.read_byte()
        if b is None or b == 0:
            return ""
        raw = self.stream.read(b)
        try:
            return raw.decode('tis-620')
        except:
            return raw.decode('latin1', errors='replace')

    def read_ident(self):
        b = self.read_byte()
        if b is None or b == 0:
            return ""
        return self.stream.read(b).decode('latin1', errors='replace')

    def parse_value(self, val_type):
        if val_type == 1: # int8
            return str(struct.unpack('b', self.stream.read(1))[0])
        elif val_type == 2: # int16
            return str(struct.unpack('<h', self.stream.read(2))[0])
        elif val_type == 3: # int32
            return str(struct.unpack('<i', self.stream.read(4))[0])
        elif val_type == 4: # float (Extended 10-byte or Double 8-byte)
            # In Delphi 32-bit, float in DFM is 10-byte extended or single/double
            # often 10 bytes:
            raw = self.stream.read(10)
            return "<float>"
        elif val_type == 5: # ShortString
            return repr(self.read_str())
        elif val_type == 6: # Ident
            return self.read_ident()
        elif val_type == 7: # False
            return "False"
        elif val_type == 8: # True
            return "True"
        elif val_type == 9: # Binary data
            length = struct.unpack('<I', self.stream.read(4))[0]
            self.stream.read(length)
            return f"<{length} bytes binary>"
        elif val_type == 10: # Set of idents
            items = []
            while True:
                s = self.read_ident()
                if not s:
                    break
                items.append(s)
            return "[" + ", ".join(items) + "]"
        elif val_type == 11: # Collection
            items = []
            while True:
                b = self.read_byte()
                if b == 0 or b is None:
                    break
                self.stream.seek(-1, io.SEEK_CUR)
                # item in collection is an object or value
                # Delphi collections have item markers (0 or sub-object)
                item_val = self.parse_collection_item()
                items.append(item_val)
            return "(\n" + "\n".join(items) + "\n" + self.pad() + ")"
        elif val_type == 12: # LString (long string, 4 bytes len)
            length = struct.unpack('<I', self.stream.read(4))[0]
            raw = self.stream.read(length)
            try:
                return repr(raw.decode('tis-620'))
            except:
                return repr(raw.decode('latin1', errors='replace'))
        elif val_type == 13: # WString
            length = struct.unpack('<I', self.stream.read(4))[0]
            raw = self.stream.read(length * 2)
            return repr(raw.decode('utf-16le', errors='replace'))
        elif val_type == 14: # Int64
            return str(struct.unpack('<q', self.stream.read(8))[0])
        else:
            return f"<unknown_type_0x{val_type:02X}>"

    def parse_collection_item(self):
        # Delphi collection item:
        # starts with item marker
        self.indent += 1
        res = [f"{self.pad()}item"]
        self.indent += 1
        while True:
            b = self.read_byte()
            if b == 0 or b is None:
                break
            self.stream.seek(-1, io.SEEK_CUR)
            prop_name = self.read_ident()
            if not prop_name:
                break
            v_type = self.read_byte()
            v_val = self.parse_value(v_type)
            res.append(f"{self.pad()}{prop_name} = {v_val}")
        self.indent -= 1
        res.append(f"{self.pad()}end")
        self.indent -= 1
        return "\n".join(res)

    def parse_object(self):
        flags = self.read_byte()
        if flags is None:
            return False
        
        type_name = self.read_ident()
        obj_name = self.read_ident()
        
        kind = "object"
        if flags & 1:
            kind = "inherited"
        if flags & 2:
            kind = "inline"
            
        self.out.append(f"{self.pad()}{kind} {obj_name}: {type_name}")
        self.indent += 1
        
        # Read properties
        while True:
            pos_before = self.stream.tell()
            b = self.read_byte()
            if b is None or b == 0:
                break # end of properties
            self.stream.seek(pos_before)
            prop_name = self.read_ident()
            if not prop_name:
                break
            v_type = self.read_byte()
            if v_type is None:
                break
            v_val = self.parse_value(v_type)
            self.out.append(f"{self.pad()}{prop_name} = {v_val}")

        # Read child objects
        while True:
            pos_before = self.stream.tell()
            b = self.read_byte()
            if b is None or b == 0:
                break # end of object
            self.stream.seek(pos_before)
            # parse child object
            self.parse_object()

        self.indent -= 1
        self.out.append(f"{self.pad()}end")
        return True

    def parse(self):
        magic = self.stream.read(4)
        if magic != b'TPF0':
            return "// NOT A TPF0 DFM"
        while self.parse_object():
            pass
        return "\n".join(self.out)

# Decompile TSDIAPPFORM
raw_main = get_rcdata('TSDIAPPFORM')
if raw_main:
    parser = DFMParser(raw_main)
    text = parser.parse()
    with open('TSDIAPPFORM.dfm.txt', 'w', encoding='utf-8') as f:
        f.write(text)
    print("TSDIAPPFORM.dfm.txt created successfully! Size:", len(text))
else:
    print("Could not find TSDIAPPFORM resource")
