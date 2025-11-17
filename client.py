# python3 client.py test_file.txt
# cliente não envia metadados do arquivo (nome, tamanho, etc)
# servidor salva como 'received_file.txt' sempre

import socket
import sys
import os
import shared_config as config

def send_and_wait(sock, server_addr, pkt_to_send, expected_ack_num):
    """
    Envia um pacote e espera por um ACK específico.
    Reimplementa a lógica de retransmissão e timeout.
    Requisito: Timer e Timeouts no Remetente
    Requisito: Retransmissões
    """
    while True:
        try:
            # 1. Envia o pacote
            sock.sendto(pkt_to_send, server_addr)
            
            # 2. Define o timeout
            sock.settimeout(config.TIMEOUT)
            
            # 3. Espera pelo ACK
            ack_pkt, _ = sock.recvfrom(config.BUFFER_SIZE)
            
            seq, ack, flags, chk, data = config.unpack_packet(ack_pkt)
            
            # 4. Verifica o ACK
            if (ack_pkt and 
                config.verify_checksum(data, chk) and 
                flags & config.ACK and 
                ack == expected_ack_num):
                
                sock.settimeout(None) # Limpa o timeout
                return seq, ack, flags # Sucesso, retorna o pacote de ACK
                
        except socket.timeout:
            # Requisito: Retransmissões em caso de Timeout
            print(f"[Cliente] TIMEOUT! Pacote (Seq={config.unpack_packet(pkt_to_send)[0]}, AckNum={expected_ack_num}) perdido. Retransmitindo...")
            # O loop continua e retransmite

def perform_handshake(sock, server_addr):
    """
    Executa o lado do cliente do 3-way handshake.
    Requisito: 3-way Handshake (equivalente)
    """
    client_seq = 200 # Sequência inicial aleatória do cliente
    
    # 1. Envia SYN
    syn_pkt = config.make_packet(client_seq, 0, config.SYN)     #make_packet(seq_num, ack_num, flags, data=b'')
    print(f"[Cliente] Enviando SYN... (Seq={client_seq})")
    
    # 2. Espera por SYN+ACK
    # Esperamos um ACK para o *nosso* SYN (client_seq + 1)
    srv_seq, srv_ack, srv_flags = send_and_wait(
        sock, server_addr, syn_pkt, client_seq + 1
    )
    
    if not (srv_flags & config.SYN and srv_flags & config.ACK):
        raise Exception("Handshake falhou: Servidor não enviou SYN+ACK")

    print(f"[Cliente] SYN+ACK recebido. (Seq={srv_seq}, Ack={srv_ack})")

    # 3. Envia o ACK final
    ack_pkt = config.make_packet(
        seq_num=client_seq + 1, 
        ack_num=srv_seq + 1, # Reconhece o SYN do servidor
        flags=config.ACK
    )
    sock.sendto(ack_pkt, server_addr)
    print(f"[Cliente] ACK final enviado. Handshake completo.")
    
    # O próximo pacote de dados terá seq = client_seq + 1
    return client_seq + 1

def send_file(sock, server_addr, filepath, next_seq):
    """
    Lê o arquivo em pedaços e os envia usando send_and_wait (Stop-and-Wait).
    """
    print(f"[Cliente] Enviando arquivo: {filepath}")
    
    try:
        with open(filepath, 'rb') as f:
            seq = next_seq
            while True:
                data = f.read(config.DATA_SIZE)
                
                # Cria pacote de dados (sem flags)
                # Requisito: Cabeçalhos com Número de Sequência
                data_pkt = config.make_packet(seq, 0, 0, data)
                
                print(f"[Cliente] Enviando pacote {seq} (Tamanho: {len(data)} bytes)...")
                send_and_wait(sock, server_addr, data_pkt, seq) # Espera ACK para este 'seq'
                print(f"[Cliente] ACK {seq} recebido.")
                
                seq += 1
                
                if not data:
                    # Envia um último pacote vazio para sinalizar "quase fim"
                    # O servidor o tratará como um pacote de dados normal.
                    # O FIN real será enviado no teardown.
                    print("[Cliente] Fim do arquivo atingido.")
                    break
        
        return seq # Retorna a última sequência usada + 1

    except FileNotFoundError:
        print(f"Erro: Arquivo '{filepath}' não encontrado.")
        return None
    except Exception as e:
        print(f"Erro ao enviar arquivo: {e}")
        return None

def perform_teardown(sock, server_addr, last_seq):
    """
    Envia o FIN para o servidor e espera o FIN+ACK.
    """
    print("[Cliente] Enviando FIN...")
    fin_pkt = config.make_packet(last_seq, 0, config.FIN)
    
    # Espera um ACK para o nosso FIN (last_seq + 1)
    _, _, flags = send_and_wait(sock, server_addr, fin_pkt, last_seq + 1)
    
    if flags & config.FIN and flags & config.ACK:
        print("[Cliente] FIN+ACK recebido do servidor.")
        # Envia o ACK final
        ack_pkt = config.make_packet(last_seq + 1, 0, config.ACK)
        sock.sendto(ack_pkt, server_addr)
        print("[Cliente] ACK final enviado. Conexão encerrada.")
    else:
        print("[Cliente] Teardown falhou (não recebeu FIN+ACK).")


def main():
    print(sys.argv)
    if len(sys.argv) != 2:
        print(f"Uso: python {sys.argv[0]} <caminho_do_arquivo>")
        return

    filepath = sys.argv[1]
    if not os.path.exists(filepath):
        print(f"Erro: Arquivo '{filepath}' não encontrado.")
        return
    if os.path.getsize(filepath) > 22 * 1024 * 1024:
        print("Erro: O arquivo é maior que 22MB.")
        return

    server_addr = (config.SERVER_HOST, config.SERVER_PORT)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    try:
        # 1. Handshake
        next_seq = perform_handshake(sock, server_addr)
        
        # 2. Envio de Dados
        last_seq = send_file(sock, server_addr, filepath, next_seq)
        
        # 3. Teardown
        if last_seq:
            perform_teardown(sock, server_addr, last_seq)
            
    except Exception as e:
        print(f"[Cliente] Erro crítico: {e}")
    finally:
        sock.close()
        print("[Cliente] Socket fechado.")

if __name__ == "__main__":
    main()