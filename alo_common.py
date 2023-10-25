import io
import struct
from enum import IntEnum

class OpType(IntEnum):
    DATA = 1
    MOVE = 2

class Op:
    def __init__(self, type: OpType) -> None:
        self.type = type

    def to_bytes(self) -> bytes:
        raise NotImplementedError()

class DataOp(Op):
    def __init__(self, virtual_address: int, data: bytes) -> None:
        super().__init__(OpType.DATA)
        self.virtual_address = virtual_address
        self.data = data

    def to_bytes(self) -> bytes:
        buf = bytearray()
        buf.extend(struct.pack('B', self.type))
        buf.extend(struct.pack('<I', self.virtual_address))
        buf.extend(struct.pack('<I', len(self.data)))
        buf.extend(self.data)
        return bytes(buf)

class MoveOp(Op):
    def __init__(self, virtual_address: int, length: int, new_virtual_address: int) -> None:
        super().__init__(OpType.MOVE)
        self.virtual_address = virtual_address
        self.length = length
        self.new_virtual_address = new_virtual_address

    def to_bytes(self) -> bytes:
        buf = bytearray()
        buf.extend(struct.pack('B', self.type))
        buf.extend(struct.pack('<I', self.virtual_address))
        buf.extend(struct.pack('<I', self.length))
        buf.extend(struct.pack('<I', self.new_virtual_address))
        return bytes(buf)

class FileOp(DataOp):
    def __init__(self, virtual_address: int, filename: str, limit_size: int) -> None:
        with open(filename, 'rb') as f:
            data = f.read().rstrip(b'\x90')

        assert(len(data) <= limit_size)
        super().__init__(virtual_address, data)

class Patch:
    def __init__(self, checksum: str, instructions: list[Op]) -> None:
        self.checksum = checksum
        self.instructions = instructions

    def to_bytes(self) -> bytes:
        buf = bytearray()
        buf.extend(bytes.fromhex(self.checksum))
        for instruction in self.instructions:
            buf.extend(instruction.to_bytes())
        return bytes(buf)
    
    @staticmethod
    def from_bytes(data):
        f = io.BytesIO(data)

        checksum: str = f.read(16).hex()

        instructions: list[Op] = []
        while f.tell() < len(data):
            op_type = OpType(struct.unpack('B', f.read(1))[0])
            if op_type == OpType.DATA:
                virtual_address = struct.unpack('<I', f.read(4))[0]
                len_data        = struct.unpack('<I', f.read(4))[0]
                instructions.append(DataOp(
                    virtual_address,
                    f.read(len_data)
                ))
            elif op_type == OpType.MOVE:
                virtual_address     = struct.unpack('<I', f.read(4))[0]
                length              = struct.unpack('<I', f.read(4))[0]
                new_virtual_address = struct.unpack('<I', f.read(4))[0]
                instructions.append(MoveOp(
                    virtual_address,
                    length,
                    new_virtual_address
                ))

        return Patch(checksum, instructions)
                