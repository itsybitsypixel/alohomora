from alo_common import *
import argparse
import hashlib
import struct
import sys

def fatal_open(filename, mode):
    try:
        f = open(filename, mode)
    except FileNotFoundError:
        print(f'Failed to open {filename}')
        sys.exit(1) 
    return f

class XBE:
    class Section:
        def __init__(self, vaddr: int, vsize: int, raddr: int, rsize: int):
            self.vaddr = vaddr
            self.vsize = vsize
            self.raddr = raddr
            self.rsize = rsize

    def __init__(self, f, sections):
        self.f = f
        self.sections = sections

    def read_bytes(self) -> bytes:
        self.f.seek(0)
        return self.f.read()

    @staticmethod
    def from_filepath(filepath):
        f = fatal_open(filepath, 'rb')

        f.seek(0x104)
        baseaddr = struct.unpack('i', f.read(4))[0]
        
        f.seek(0x11c)
        num_sections = struct.unpack('i', f.read(4))[0]
        
        f.seek(0x120)
        vaddr_sections = struct.unpack('i', f.read(4))[0]

        sections = []
        for i in range(num_sections):
            f.seek((vaddr_sections - baseaddr) + 0x38 * i)
            
            f.seek(4, 1)
            vaddr = struct.unpack('i', f.read(4))[0]
            vsize = struct.unpack('i', f.read(4))[0]
            raddr = struct.unpack('i', f.read(4))[0]
            rsize = struct.unpack('i', f.read(4))[0]
            sections.append(XBE.Section(vaddr, vsize, raddr, rsize))

        return XBE(f, sections)

    def virtual_address_to_raw_address(self, vaddr):
        for i in range(len(self.sections)):
            section = self.sections[i]
            if vaddr >= section.vaddr and vaddr < section.vaddr + section.vsize:
                return (vaddr - section.vaddr) + section.raddr
        return None

if __name__ == '__main__':
    args_parser = argparse.ArgumentParser()
    args_parser.add_argument('xbe_filename')
    args_parser.add_argument('-p', '--patch-filename',  required=True, help='filename of patch file')
    args_parser.add_argument('-o', '--output-filename', required=True, help='filename of patched output xbe')
    args = args_parser.parse_args()

    xbe = XBE.from_filepath(args.xbe_filename)
    xbe_bytes = xbe.read_bytes()
    xbe_checksum = hashlib.md5(xbe_bytes).hexdigest()

    patches: list[Patch] = []
    with fatal_open(args.patch_filename, 'rb') as f:
        num_patches = struct.unpack('<I', f.read(4))[0]
        for i in range(num_patches):
            len_patch = struct.unpack('<I', f.read(4))[0]
            patches.append(Patch.from_bytes(f.read(len_patch)))

    matched_patch: Patch = None
    for patch in patches:
        if xbe_checksum.casefold() == patch.checksum.casefold(): 
            matched_patch = patch
            break

    if matched_patch == None:
        print('Could not find patch that matches checksum of provided xbe. Please make sure you\'re using an unmodified executable.')
        sys.exit(1)

    modified_bytes = bytearray(xbe_bytes)
    for instruction in matched_patch.instructions:
        if instruction.type == OpType.DATA:
            raw_address = xbe.virtual_address_to_raw_address(instruction.virtual_address)

            modified_bytes[raw_address:raw_address+len(instruction.data)] = instruction.data
        elif instruction.type == OpType.MOVE:
            raw_address = xbe.virtual_address_to_raw_address(instruction.virtual_address)
            new_raw_address = xbe.virtual_address_to_raw_address(instruction.new_virtual_address)
            data = modified_bytes[raw_address:raw_address+instruction.length]

            modified_bytes[new_raw_address:new_raw_address+len(data)] = data

    with fatal_open(args.output_filename, 'wb') as f:
        f.write(modified_bytes)

    print('OK')
