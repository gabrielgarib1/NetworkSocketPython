#Ctrl+C to stop the server
#python3 server.py [0|1|2]
#0 - Normal Mode (default)
#1 - Single Failure Simulation Mode
#2 - Fuzzing Simulation Mode
import socket
import shared_config as config
import os
import sys
import random 

def wait_for_handshake(sock):
    """
    Executa o lado do servidor do 3-way handshake.
    Requisito: 3-way Handshake (equivalente)
    """
    print(f"[Servidor] Esperando por conexões em {config.SERVER_HOST}:{config.SERVER_PORT}...")
    sock.settimeout(None) # Garante que o socket está no modo de espera infinita
    # 1. Espera pelo SYN do cliente
    syn_pkt, client_addr = sock.recvfrom(config.BUFFER_SIZE)
    seq, ack, flags, chk, data = config.unpack_packet(syn_pkt)
    
    if not (flags & config.SYN and config.verify_checksum(data, chk)):
        print("[Servidor] Pacote SYN inválido recebido. Ignorando.")
        return None, None
        
    print(f"[Servidor] SYN recebido de {client_addr}. (Seq={seq})")
    
    # 2. Envia SYN+ACK
    client_seq = seq
    server_seq = 100  # Sequência inicial do servidor
    
    # Requisito: Mensagens de Reconhecimento (ACK)
    syn_ack_pkt = config.make_packet(
        seq_num=server_seq,
        ack_num=client_seq + 1,  # Reconhece o SYN do cliente
        flags=config.SYN | config.ACK
    )
    sock.sendto(syn_ack_pkt, client_addr)
    print(f"[Servidor] SYN+ACK enviado. (Seq={server_seq}, Ack={client_seq + 1})")

    # 3. Espera pelo ACK final
    # (Este passo é simplificado; um servidor real teria um timeout aqui)
    try:
        sock.settimeout(config.TIMEOUT * 2) # Espera um pouco mais pelo ACK final
        ack_pkt, _ = sock.recvfrom(config.BUFFER_SIZE)
        seq, ack, flags, chk, data = config.unpack_packet(ack_pkt)
        
        if (flags & config.ACK and 
            ack == server_seq + 1 and 
            config.verify_checksum(data, chk)):
            
            print(f"[Servidor] Handshake completo. Conexão estabelecida com {client_addr}.")
            sock.settimeout(None) # Limpa o timeout para a fase de dados
            return client_addr, client_seq + 1 # Retorna o próximo SEQ esperado do cliente
        else:
            print("[Servidor] ACK final do handshake inválido.")
            return None, None
            
    except socket.timeout:
        print("[Servidor] Timeout esperando pelo ACK final do handshake.")
        return None, None

def receive_file(sock, client_addr, expected_seq,simulation_mode="normal"):
    """
    Recebe o arquivo do cliente, tratando pacotes duplicados ou fora de ordem.
    Usa um protocolo "Stop-and-Wait".
    """
    # --- Flags de estado para a Simulação de Falha Únicas ---
    packet_has_been_dropped = False
    packet_to_drop = expected_seq + 1  # O segundo pacote de dados
    
    # --- Constantes para a Simulação Fuzzing ---
    LOSS_CHANCE = 0.3      # 15% de chance de perder o pacote
    CORRUPTION_CHANCE = 0.05 # 5% de chance de corromper

    print("[Servidor] Esperando pelo arquivo...")
    base_output_name = 'received_file.txt'
    output_filename = find_available_filename(base_output_name)
    print(f"[Servidor] Salvando arquivo como: {output_filename}")
    
    with open(output_filename, 'wb') as f:
        while True:
            try:
                pkt, addr = sock.recvfrom(config.BUFFER_SIZE)
                if addr != client_addr:
                    continue # Ignora pacotes de outros clientes
# --- 2. LÓGICA DE FUZZING (ANTES de desempacotar) ---
                if simulation_mode == "fuzzing":
                    # Simular Perda de Pacote
                    if random.random() < LOSS_CHANCE:
                        print(f"[SIMULAÇÃO FUZZING] Pacote PERDIDO.")
                        continue # Descarta o pacote
                    
                    # Simular Corrupção de Pacote
                    if random.random() < CORRUPTION_CHANCE:
                        print(f"[SIMULAÇÃO FUZZING] Pacote CORROMPIDO.")
                        pkt = b'corrupted_bytes' + pkt # Adiciona lixo ao pacote
                # --- FIM DO FUZZING ---
                seq, ack, flags, checksum, data = config.unpack_packet(pkt)

                if seq is None:
                    print("[Servidor] Pacote inválido recebido. Descartando.")
                    continue
                # Verifica se o pacote é válido
 # --- 3. LÓGICA DE FALHA ÚNICA (DEPOIS de desempacotar) ---
                if (simulation_mode == "falha_unica" and 
                    seq == packet_to_drop and 
                    not packet_has_been_dropped):
                    
                    print(f"[SIMULAÇÃO FALHA ÚNICA] Ignorando pacote {seq} de propósito!")
                    packet_has_been_dropped = True
                    continue
                # --- FIM DA FALHA ÚNICA ---
# 4. Verificação de Checksum (pegará pacotes corrompidos pelo fuzzing)
                if not config.verify_checksum(data, checksum):
                    print("[Servidor] Pacote corrupto recebido. Descartando.")
                    continue
                # --- Lógica de Teardown (FIN) ---
                if flags & config.FIN:
                    print(f"[Servidor] FIN recebido (Seq={seq}). Encerrando.")
                    # Envia FIN+ACK
                    fin_ack_pkt = config.make_packet(
                        seq_num=0, # Seq do servidor não importa aqui
                        ack_num=seq + 1,
                        flags=config.FIN | config.ACK
                    )
                    sock.sendto(fin_ack_pkt, client_addr)
                    
                    # Espera ACK final (simplificado, sem retransmissão)
                    sock.settimeout(config.TIMEOUT * 2)
                    try:
                        ack_pkt, _ = sock.recvfrom(config.BUFFER_SIZE)
                        # ... (verificar se é o ACK correto) ...
                        print("[Servidor] ACK final do cliente recebido.")
                    except socket.timeout:
                        print("[Servidor] Timeout no ACK final. Encerrando mesmo assim.")

                    print(f"[Servidor] Arquivo '{output_filename}' salvo com sucesso.")
                    return True # Encerra a função

                # --- Lógica de Dados ---
                if flags == 0: # Pacote de dados puro
                    # Requisito: Reconhecimento (ACK)
                    if seq == expected_seq:
                        # Pacote correto e esperado
                        f.write(data)
                        print(f"[Servidor] Pacote {seq} recebido e salvo. Enviando ACK {seq}.")
                        ack_pkt = config.make_packet(0, seq, config.ACK)
                        sock.sendto(ack_pkt, client_addr)
                        expected_seq += 1 # Espera o próximo
                    
                    elif seq < expected_seq:
                        # Pacote duplicado (provavelmente ACK anterior se perdeu)
                        print(f"[Servidor] Pacote duplicado {seq} recebido. Reenviando ACK {seq}.")
                        ack_pkt = config.make_packet(0, seq, config.ACK)
                        sock.sendto(ack_pkt, client_addr)
                    
                    # else (seq > expected_seq): Pacote fora de ordem. 
                    # No Stop-and-Wait, simplesmente descartamos e esperamos
                    # o timeout do cliente.
            
            except socket.timeout:
                print("[Servidor] Timeout esperando por dados. (Isso não deveria acontecer)")
                continue
            except Exception as e:
                print(f"[Servidor] Erro: {e}")
                return False

def find_available_filename(base_name):
    """
    Verifica se 'base_name' existe. Se sim, tenta 'base_name(1)', 'base_name(2)', etc.
    """
    # Separa o nome do arquivo da extensão (ex: "file", ".txt")
    base, ext = os.path.splitext(base_name)
    
    output_filename = base_name
    counter = 1
    
    # Loop: enquanto o nome do arquivo já existir...
    while os.path.exists(output_filename):
        # ...crie um novo nome com um contador
        output_filename = f"{base}{counter}{ext}"
        counter += 1
        
    return output_filename

def main():
    simulation_mode = "normal"  # Padrão
    
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == '1':
            simulation_mode = "falha_unica"
            print("="*40)
            print("[Servidor] MODO SIMULAÇÃO (FALHA ÚNICA) ATIVADO.")
            print("O servidor irá ignorar o segundo pacote de dados.")
            print("="*40)
        elif arg == '2':
            simulation_mode = "fuzzing"
            print("="*40)
            print("[Servidor] MODO SIMULAÇÃO (FUZZING) ATIVADO.")
            print("O servidor irá perder e corromper pacotes aleatoriamente.")
            print("="*40)
        elif arg != '0':
            print(f"Argumento '{arg}' não reconhecido. Rodando em modo normal.")
    # --- Fim da Lógica ---

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # define conf do socket (AF_NET indica IPv_4 e SOCK_DGRAM indica UDP)
    sock.bind((config.SERVER_HOST, config.SERVER_PORT))

    print(f"\n[Servidor] Servidor iniciado em modo: {simulation_mode.upper()}")
    try:
        while True:
            client_addr, next_seq = wait_for_handshake(sock)
            
            if client_addr:
                if receive_file(sock, client_addr, next_seq,simulation_mode):
                    print("[Servidor] Transmissão concluída. Pronto para nova conexão.")
                    print("-" * 30)
    except KeyboardInterrupt:
        print("\n[Servidor] Encerrando servidor.")
    finally:
        print("[Servidor] Fechando socket.")
        sock.close()
if __name__ == "__main__":
    main()