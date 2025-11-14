
import socket

server_ip='localhost'    #server ip: 127.0.0.1
server_port=5000    #server port

udp=socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
udp.connect((server_ip,server_port))
message=input("Enter your message: ")
udp.sendto(message.encode(), (server_ip,server_port))
udp.close()