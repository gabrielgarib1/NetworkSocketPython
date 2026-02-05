# python3 client.py test_file.txt
# cliente não envia metadados do arquivo (nome, tamanho, etc)
# servidor salva como 'received_file.txt' sempre

import socket
import sys
import os
import shared_config as config
import time as t

#Classe para cálculo do Timeout e RTT

class RTTState:
    def __init__(self, initial_timeout=1.0):
        # Constantes do TCP para suavização (alpha = 1/8, beta = 1/4)
        self.alpha = 0.125 
        self.beta = 0.25   
        
        # Variáveis de Estado
        self.srtt = initial_timeout   # RTT Suavizado (Smoothed RTT)
        self.rttvar = initial_timeout / 2 # Variação do RTT (Deviation)
        self.rto = initial_timeout    # Timeout de Retransmissão (RTO)
        self.is_first_measurement = True

    def update_rto(self, measured_rtt):
        """Calcula o novo SRTT, RTTVAR e o RTO (SRTT + 4 * RTTVAR)."""
        
        if self.is_first_measurement:
            # Para a primeira medição, inicializa diretamente
            self.srtt = measured_rtt
            self.rttvar = measured_rtt / 2
            self.is_first_measurement = False
        else:
            # Fórmula de Suavização:
            diff = abs(self.srtt - measured_rtt)
            
            # Atualiza RTTVAR (Variação)
            # RTTVAR = (1 - β) * RTTVAR + β * |SRTT - RTT_medido|
            self.rttvar = (1 - self.beta) * self.rttvar + self.beta * diff
            
            # Atualiza SRTT (Tempo Suavizado)
            # SRTT = (1 - α) * SRTT + α * RTT_medido
            self.srtt = (1 - self.alpha) * self.srtt + self.alpha * measured_rtt
            
        # Calcula o novo RTO (RTO = SRTT + 4 * RTTVAR)
        # 4 * RTTVAR adiciona uma margem de segurança ao timer
        self.rto = self.srtt + 4 * self.rttvar
        
        # Garante um RTO mínimo (ex: 100ms)
        if self.rto < 0.1:
            self.rto = 0.1
            
        return self.rto

# Rotinas auxiliares 
def send_and_wait(sock, server_addr, pkt_to_send, expected_ack_num, rtt_state: RTTState):
    """
    Envia um pacote e espera por um ACK específico.
    Reimplementa a lógica de retransmissão e timeout.
    Requisito: Timer e Timeouts no Remetente
    Requisito: Retransmissões
    """

    retransmission_count = 0
    while True:
        # --- CORREÇÃO: Define current_rto antes do try ---
        current_rto = rtt_state.rto
        try:
            # 1. Medição do RTT: inicio
            time_sent = t.time()

            # 2. Envia o pacote
            sock.sendto(pkt_to_send, server_addr)
            
            # 3. Define o timeout
            sock.settimeout(config.TIMEOUT)
            
            # 4. Espera pelo ACK
            ack_pkt, _ = sock.recvfrom(config.BUFFER_SIZE)
            
            seq, ack, flags, chk, data = config.unpack_packet(ack_pkt)
            # 5. RTT fim -> recebimento do ACK
            time_ack_received = t.time()

            # desempacotamento e verificação

            # 6. Verifica o ACK
            if (ack_pkt and 
                config.verify_checksum(data, chk) and 
                flags & config.ACK and 
                ack == expected_ack_num):

                # ATUALIZAÇÃO DO RTO APÓS SUCESSO
                measured_rtt = time_ack_received - time_sent
                new_rto = rtt_state.update_rto(measured_rtt)
                
                print(f"[Cliente] ACK {expected_ack_num} recebido. RTT: {measured_rtt:.4f}s. Novo RTO: {new_rto:.4f}s")
                
                sock.settimeout(None) # Limpa o timeout
                return seq, ack, flags # Sucesso, retorna o pacote de ACK
                
        except socket.timeout:
            # 7. Ação em caso de TIMEOUT
            retransmission_count += 1
            print(f"[Cliente] TIMEOUT! Retransmitindo (Tentativa {retransmission_count}). RTO atual: {current_rto:.4f}s")
            # BACKOFF EXPONENCIAL: Dobra o RTO para a próxima tentativa
            rtt_state.rto *= 2


def perform_handshake(sock, server_addr,rtt_state: RTTState):
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
        sock, server_addr, syn_pkt, client_seq + 1, rtt_state
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

def send_file(sock, server_addr, filepath, next_seq, rtt_state: RTTState):
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
                send_and_wait(sock, server_addr, data_pkt, seq, rtt_state) # Espera ACK para este 'seq'
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

def perform_teardown(sock, server_addr, last_seq, rtt_state: RTTState):
    """
    Envia o FIN para o servidor e espera o FIN+ACK.
    """
    print("[Cliente] Enviando FIN...")
    fin_pkt = config.make_packet(last_seq, 0, config.FIN)
    
    # Espera um ACK para o nosso FIN (last_seq + 1)
    _, _, flags = send_and_wait(sock, server_addr, fin_pkt, last_seq + 1, rtt_state)
    
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
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # Definição do tipo de socket

    # --- ALTERAÇÃO: 1. Inicializa o objeto de estado RTT ---
    # Usa o TIMEOUT fixo inicial do config como ponto de partida
    rtt_state = RTTState(initial_timeout=config.TIMEOUT)
    
    try:
        # 1. Handshake
        next_seq = perform_handshake(sock, server_addr, rtt_state)
        
        # 2. Envio de Dados
        last_seq = send_file(sock, server_addr, filepath, next_seq, rtt_state)
        
        # 3. Teardown
        if last_seq:
            perform_teardown(sock, server_addr, last_seq, rtt_state)
            
    except Exception as e:
        print(f"[Cliente] Erro crítico: {e}")
    finally:
        sock.close()
        print("[Cliente] Socket fechado.")

if __name__ == "__main__":
    main()