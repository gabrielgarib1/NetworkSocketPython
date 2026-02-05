# Linux/macOS: diff test_file.txt received_file.txt 

# Windows: fc /b test_file.txt received_file.txt

import struct   #for byte packing/unpacking
import zlib    #for checksum calculation   


# --- Configurações do Servidor ---
SERVER_HOST = '127.0.0.1' # Localhost de Cria.
SERVER_PORT = 5000

# --- Configurações do Protocolo ---
BUFFER_SIZE = 1472  # Tamanho máximo do datagrama UDP (MTU comum) 1500 - 20 (IP header) - 8 (UDP header)
TIMEOUT = 0.1       

# --- Flags do Protocolo (semelhante ao TCP) ---
SYN = 1 << 0  # 1
ACK = 1 << 1  # 2
FIN = 1 << 2  # 4

# --- Estrutura do Cabeçalho ---
# L = 'unsigned long' (4 bytes)
# H = 'unsigned short' (2 bytes)
# ! = Ordem de rede (big-endian) --> a way for a computer to arrange bytes in a specific order
# Sequência (4) + ACK Num (4) + Flags (2)
HEADER_FORMAT = '!LLH'
HEADER_SIZE = struct.calcsize(HEADER_FORMAT) # 10 bytes

# Payload size = buffer size - header size - checksum size(4 bytes)
DATA_SIZE = BUFFER_SIZE - HEADER_SIZE - 4  

def make_packet(seq_num, ack_num, flags, data=b''):

    # 1. Cria o cabeçalho
    header = struct.pack(HEADER_FORMAT, seq_num, ack_num, flags)
    
    checksum = zlib.crc32(data) # Calcula o checksum dos dados
    checksum_packed = struct.pack('!L', checksum)   # Empacota o checksum como L (4 bytes)
    
    return header + checksum_packed + data      #Concatena tudo e retorna o pacote completo

def unpack_packet(packet):

    try:
        # 1. Desempacota o cabeçalho
        header = packet[:HEADER_SIZE]
        seq_num, ack_num, flags = struct.unpack(HEADER_FORMAT, header)
        
        # 2. Desempacota o checksum
        checksum_packed = packet[HEADER_SIZE : HEADER_SIZE + 4]
        checksum = struct.unpack('!L', checksum_packed)[0]
        
        # 3. Extrai os dados
        data = packet[HEADER_SIZE + 4 :]
        
        return seq_num, ack_num, flags, checksum, data
    except struct.error:
        # Pacote malformado ou curto
        return None, None, None, None, None

def verify_checksum(data, checksum):
    """
    Verifica se o checksum recebido corresponde ao checksum calculado dos dados.
    """
    return zlib.crc32(data) == checksum